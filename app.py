import json
import math
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import mean, median, median_low
from threading import Lock
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

IDX = os.environ.get("IDX_BIN") or shutil.which("idx") or str(
    Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "bin/idx"
)
HORIZONS = (1, 5)
SCAN_LOCK = Lock()
JAKARTA = ZoneInfo("Asia/Jakarta")
EXIT_TIME = "15:45"


def idx(*args):
    result = subprocess.run(
        [IDX, "-o", "json", "--timeout", "8", *args],
        capture_output=True, text=True, timeout=35, check=True,
    )
    return json.loads(result.stdout)["data"]


def outcomes(prices, horizon):
    samples = []
    state = None
    for i in range(20, len(prices)):
        past = prices[i - 20:i + 1]
        if None in past:
            continue
        close = past[-1][0]
        momentum = (close > past[-6][0]) + 2 * (close > mean(p[0] for p in past))
        if i == len(prices) - 1:
            state = momentum
        future = prices[i + 1:i + horizon + 1]
        if len(future) == horizon and None not in future:
            change = future[-1][0] / close - 1
            upside = max(p[1] for p in future) / close - 1
            samples.append((i, momentum, change, upside))
    return samples, state


def estimate(samples, state, index, horizon):
    known = [row for row in samples if row[0] + horizon <= index]
    matches = [row for row in known if row[1] == state]
    if len(matches) < 30:
        return None
    baseline = mean(row[2] > 0 for row in known)
    probability = (sum(row[2] > 0 for row in matches) + 10 * baseline) / (len(matches) + 10)
    return probability, median(row[2] for row in matches), median(row[3] for row in matches), baseline


def evaluate(samples, state, index, horizon):
    current = estimate(samples, state, index, horizon)
    if current is None:
        return None

    checks = []
    for i, regime, change, upside in samples:
        if i < index - 120 or i + horizon > index:
            continue
        prediction = estimate(samples, regime, i, horizon)
        if prediction is None:
            continue
        probability, projected, target, baseline = prediction
        up = change > 0
        tp = upside >= target if probability >= .55 and projected > 0 and target > 0 else None
        checks.append(((probability >= .5) == up, (probability - up) ** 2, (baseline - up) ** 2, tp))

    if len(checks) < 40:
        return None
    accuracy, brier, baseline_brier, targets = zip(*checks)
    hits = [hit for hit in targets if hit is not None]
    probability, change, target, _ = current
    return {
        "probability": probability, "change": change, "target": target,
        "accuracy": mean(accuracy), "brier": mean(brier), "baseline_brier": mean(baseline_brier),
        "tp_hit": mean(hits) if hits else None, "tp_n": len(hits), "test_n": len(checks),
    }


def history(symbol):
    return idx("stocks", "history", symbol, "--period", "2y", "--interval", "1d", "--limit", "0")["candles"]



def replay_trade(days, entry, target, risk):
    tp = entry * (1 + target)
    stop = entry * (1 - risk)
    if not stop < days[0][0][1]["open"] <= entry:
        return None
    for session, bars in enumerate(days, 1):
        for clock, bar in bars:
            if session == len(days) and clock == EXIT_TIME:
                return "time", session, clock
            if bar["open"] >= tp:
                return "tp", session, clock
            # With both levels inside a single candle, use the adverse outcome.
            if bar["low"] <= stop:
                return "stop", session, clock
            if bar["high"] >= tp:
                return "tp", session, clock
    return "time", len(days), EXIT_TIME


def intraday_days(symbol, sessions):
    bars = idx("stocks", "history", symbol, "--period", "1mo",
               "--interval", "15m", "--limit", "0")["candles"]
    daily = {}
    for bar in bars:
        moment = datetime.fromisoformat(bar["time"]).astimezone(JAKARTA)
        values = [bar[key] for key in ("open", "high", "low", "close")]
        if not all(isinstance(value, (int, float)) and math.isfinite(value) and value > 0
                   for value in values):
            continue
        if bar["low"] <= min(bar["open"], bar["close"]) <= max(bar["open"], bar["close"]) <= bar["high"]:
            daily.setdefault(moment.date().isoformat(), {})[moment.strftime("%H:%M")] = bar

    complete = {}
    for day in sessions:
        friday = date.fromisoformat(day).weekday() == 4
        minutes = [*range(9 * 60, 690 if friday else 720, 15),
                   *range(840 if friday else 810, 946, 15)]
        expected = [f"{minute // 60:02d}:{minute % 60:02d}" for minute in minutes]
        available = daily.get(day, {})
        if all(clock in available for clock in expected):
            complete[day] = [(clock, available[clock]) for clock in expected]
    return complete


def add_trade_plans(symbol, rows, sessions):
    try:
        intraday = intraday_days(symbol, sessions)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        intraday = {}

    for horizon, row in rows:
        previous_closes = row.pop("_previous_closes")
        risk = row.pop("_risk")
        exits = []
        # shortcut: one month of intraday coverage, use a longer archive to validate timing.
        for i in range(len(sessions) - horizon, 0, -horizon):
            days = sessions[i:i + horizon]
            entry = previous_closes.get(sessions[i - 1])
            if entry and all(day in intraday for day in days):
                result = replay_trade([intraday[day] for day in days], entry, row["target"], risk)
                if result is not None:
                    exits.append(result)

        hits = [(session, clock) for kind, session, clock in exits if kind == "tp"]
        typical = median_low(hits) if len(hits) >= 3 else None
        row["plan"] = {
            "entry_limit": row["close"], "entry_time": "09:00",
            "stop": row["close"] * (1 - risk), "risk": risk,
            "deadline": EXIT_TIME, "sample": len(exits), "hits": len(hits),
            "stops": sum(kind == "stop" for kind, _, _ in exits),
            "timed_exits": sum(kind == "time" for kind, _, _ in exits),
            "tp_window": {"session": typical[0], "start": typical[1]} if typical else None,
        }


def analyze(stock, sessions):
    try:
        candles = {bar["time"][:10]: bar for bar in history(stock["symbol"])}
        prices = []
        for day in sessions:
            bar = candles.get(day)
            close, high = (bar["close"], bar["high"]) if bar else (None, None)
            valid = all(isinstance(value, (int, float)) and math.isfinite(value) and value > 0
                        for value in (close, high))
            prices.append((close, high) if valid and high >= close else None)

        last = candles.get(sessions[-1], {}).get("close")
        close = last if isinstance(last, (int, float)) and 0 < last < math.inf else None
        if None in prices[-20:]:
            return "skipped", {}, close
        turnover = median(candles[day]["volume"] * candles[day]["close"] for day in sessions[-20:])
        if turnover < 5_000_000_000:
            return "skipped", {}, close

        recent = [candles[day] for day in sessions[-20:]]
        ranges = [bar["high"] - bar["low"] for bar in recent
                  if isinstance(bar["low"], (float, int)) and 0 < bar["low"] <= bar["close"]]
        if len(ranges) != len(recent):
            return "skipped", {}, close
        close = prices[-1][0]
        risk = min(.10, max(.01, median(ranges) / close))
        previous_closes = {day: candles[day]["close"] for day in sessions[-32:]
                           if day in candles and isinstance(candles[day]["close"], (int, float))
                           and 0 < candles[day]["close"] < math.inf}

        rows = {}
        for horizon in HORIZONS:
            samples, state = outcomes(prices, horizon)
            result = evaluate(samples, state, len(prices) - 1, horizon)
            if not result:
                continue
            qualified = (result["probability"] >= .55 and result["change"] > 0
                         and result["target"] > 0 and result["tp_n"] >= 10
                         and result["brier"] < result["baseline_brier"])
            rows[str(horizon)] = {
                **result, "symbol": stock["symbol"], "name": stock["name"],
                "close": close, "qualified": qualified,
            }
            if qualified:
                rows[str(horizon)].update(tp=close * (1 + result["target"]),
                                          _risk=risk, _previous_closes=previous_closes)
        return "analyzed", rows, close
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return "failed", {}, None


def latest_sessions():
    now = datetime.now(JAKARTA)
    # shortcut: conservative cutoff for today's candle, use an exchange session feed for intraday scans.
    sessions = sorted({
        bar["time"][:10] for bar in history("^JKSE")
        if bar["time"][:10] < now.date().isoformat()
        or (bar["time"][:10] == now.date().isoformat() and now.hour >= 17)
    })
    if len(sessions) < 120 or sessions[-1] < (now.date() - timedelta(days=7)).isoformat():
        raise ValueError("Data sesi IHSG terlalu lama atau tidak cukup untuk analisis.")

    return sessions


def listed_stocks():
    return [{"symbol": row["symbol"], "name": row["name"]}
            for row in idx("stocks", "list")["instruments"]]


def lookup_stock(symbol):
    stock = next((row for row in listed_stocks() if row["symbol"] == symbol), None)
    if stock is None:
        return None
    sessions = latest_sessions()
    status, rows, close = analyze(stock, sessions)
    if status == "failed":
        raise ValueError("Riwayat saham tidak dapat diambil. Coba lagi.")
    rows = {horizon: row for horizon, row in rows.items() if row["qualified"]}
    if rows:
        add_trade_plans(symbol, [(int(horizon), row) for horizon, row in rows.items()], sessions[-31:])
    return {
        "stock": {**stock, "close": close}, "date": sessions[-1], "status": status,
        "ranks": {str(horizon): [rows[str(horizon)]] if str(horizon) in rows else []
                  for horizon in HORIZONS},
    }


def scan():
    sessions = latest_sessions()
    listed = {row["symbol"] for row in listed_stocks()}
    prefilter = idx("stocks", "screen", "-f", "mcap>1T", "--sort", "volume", "-n", "90")
    stocks = [row for row in prefilter["rows"] if row["symbol"] in listed]
    if not stocks:
        raise ValueError("Sumber data tidak mengembalikan saham untuk dipindai.")

    counts = dict(analyzed=0, skipped=0, failed=0)
    ranks = {str(horizon): [] for horizon in HORIZONS}
    universe = {str(horizon): [] for horizon in HORIZONS}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for status, rows, _ in pool.map(lambda stock: analyze(stock, sessions), stocks):
            counts[status] += 1
            for horizon, row in rows.items():
                universe[horizon].append({
                    "symbol": row["symbol"], "close": row["close"],
                    "up": round(row["probability"], 3), "change": round(row["change"], 4),
                    "accuracy": round(row["accuracy"], 3), "test_n": row["test_n"],
                    "brier_edge": round(row["baseline_brier"] - row["brier"], 4),
                    "qualified": row["qualified"],
                })
                if row["qualified"]:
                    ranks[horizon].append(row)
    for rows in ranks.values():
        rows.sort(key=lambda row: (row["probability"], row["change"]), reverse=True)
        del rows[20:]
    plans = {}
    for horizon, rows in ranks.items():
        for row in rows:
            plans.setdefault(row["symbol"], []).append((int(horizon), row))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda item: add_trade_plans(*item, sessions[-31:]), plans.items()))
    return {"date": sessions[-1], "listed": len(listed), "selected": len(stocks),
            "quoted": prefilter["quoted"], "counts": counts, "ranks": ranks, "universe": universe}


class Handler(BaseHTTPRequestHandler):
    def send_body(self, status, mime, body):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, value):
        self.send_body(status, "application/json", json.dumps(value, allow_nan=False).encode())

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path not in ("/stocks", "/stock"):
            self.send_error(404)
            return
        try:
            if url.path == "/stocks":
                self.send_json(200, listed_stocks())
                return
            symbol = parse_qs(url.query).get("symbol", [""])[0].strip().upper()
            result = lookup_stock(symbol)
            if result is None:
                self.send_json(404, {"error": "Kode saham tidak ditemukan."})
                return
            self.send_json(200, result)
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as error:
            self.log_error("Lookup failed: %s", error)
            message = str(error) if type(error) is ValueError else "Gagal membaca data IDX. Coba lagi."
            self.send_json(502, {"error": message})

    def do_POST(self):
        if self.path != "/scan":
            self.send_error(404)
            return
        if self.headers.get("Origin") not in (None, "http://127.0.0.1:8765"):
            self.send_error(403)
            return
        if not SCAN_LOCK.acquire(blocking=False):
            self.send_json(409, {"error": "Pemindaian sedang berjalan. Coba lagi sebentar."})
            return
        try:
            self.send_json(200, scan())
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as error:
            self.log_error("Scan failed: %s", error)
            message = str(error) if type(error) is ValueError else "Gagal membaca data IDX. Coba lagi."
            self.send_json(502, {"error": message})
        finally:
            SCAN_LOCK.release()


if __name__ == "__main__":
    with ThreadingHTTPServer(("127.0.0.1", 8765), Handler) as server:
        print("IDX API — http://127.0.0.1:8765", flush=True)
        server.serve_forever()
