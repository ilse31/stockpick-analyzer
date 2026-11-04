<script setup>
import { useStockScreener } from "./lib/useStockScreener";

useHead({
  title: "Stockpick · Screener BEI",
  htmlAttrs: { lang: "id" },
});

const {
  horizon,
  stockResult,
  query,
  showSuggestions,
  directoryLoading,
  directoryError,
  suggestions,
  candidates,
  aiContext,
  status,
  pending,
  openSuggestions,
  closeSuggestions,
  onSearchBlur,
  search,
  showScreener,
  loadAiUniverse,
  scan,
} = useStockScreener();

const searchInput = ref(null);
const suggestionsList = ref(null);

const percent = new Intl.NumberFormat("id-ID", {
  style: "percent",
  maximumFractionDigits: 1,
});
const rupiah = new Intl.NumberFormat("id-ID", {
  style: "currency",
  currency: "IDR",
  maximumFractionDigits: 2,
});
</script>

<template>
  <main>
    <header>
      <div class="brand">Stockpick <span>·</span> Bursa Efek Indonesia</div>
      <h1>Screener saham</h1>
      <p>
        Pindai kandidat naik di BEI atau buka analisis saham yang kamu pilih.
      </p>
    </header>

    <section class="workspace" aria-label="Alat analisis saham">
      <form
        class="search-form"
        @submit.prevent="search()"
        @focusout="onSearchBlur"
        @keydown.esc="
          closeSuggestions();
          searchInput.focus();
        "
      >
        <label class="control-label" for="stock-query">Cari saham</label>
        <div class="search-field">
          <input
            id="stock-query"
            ref="searchInput"
            v-model="query"
            type="search"
            placeholder="Kode atau nama perusahaan"
            autocomplete="off"
            @focus="openSuggestions"
            @input="openSuggestions"
            @keydown.down.prevent="
              suggestionsList?.querySelector('button')?.focus()
            "
          />
          <button
            type="submit"
            class="search-button"
            :disabled="!!pending || !query.trim()"
          >
            Lihat
          </button>
          <div v-if="showSuggestions && query.trim()" class="suggestions">
            <ul
              v-if="suggestions.length"
              ref="suggestionsList"
              aria-label="Saham yang cocok"
            >
              <li v-for="stock in suggestions" :key="stock.symbol">
                <button
                  type="button"
                  :disabled="!!pending"
                  @click="search(stock.symbol)"
                >
                  <strong>{{ stock.symbol }}</strong
                  ><span>{{ stock.name }}</span>
                </button>
              </li>
            </ul>
            <p v-else role="status">
              {{
                directoryLoading
                  ? "Memuat daftar saham…"
                  : directoryError
                    ? "Daftar saham gagal dimuat. Masukkan kode saham untuk mencari."
                    : "Tidak ada saham yang cocok."
              }}
            </p>
          </div>
        </div>
      </form>

      <div class="actions">
        <fieldset>
          <legend class="control-label">Horizon</legend>
          <div class="segments">
            <label v-for="days in ['1', '5']" :key="days">
              <input
                v-model="horizon"
                type="radio"
                name="horizon"
                :value="days"
              />
              <span>{{ days }} sesi</span>
            </label>
          </div>
        </fieldset>
        <button
          type="button"
          class="scan-button"
          :disabled="!!pending"
          @click="scan"
        >
          {{ pending === "scan" ? "Memindai…" : "Pindai saham" }}
        </button>
      </div>
    </section>

    <section
      v-if="stockResult"
      class="stock-summary"
      aria-label="Saham dipilih"
    >
      <div>
        <h2>{{ stockResult.stock.symbol }}</h2>
        <p>{{ stockResult.stock.name }}</p>
      </div>
      <div class="stock-price">
        <small>Penutupan · {{ stockResult.date }}</small>
        <strong>{{
          stockResult.stock.close === null
            ? "Tidak tersedia"
            : rupiah.format(stockResult.stock.close)
        }}</strong>
      </div>
      <button type="button" class="back-button" @click="showScreener">
        Kembali ke screener
      </button>
    </section>

    <p class="result-status" role="status">{{ status }}</p>
    <div
      class="panel"
      v-if="candidates.length"
      role="region"
      aria-label="Peringkat kandidat saham"
      tabindex="0"
    >
      <table aria-label="Hasil screener">
        <thead>
          <tr>
            <th scope="col">Saham</th>
            <th scope="col">Rentang entry</th>
            <th scope="col">Peluang naik</th>
            <th scope="col">Estimasi perubahan</th>
            <th scope="col">Target TP</th>
            <th scope="col">Stop-loss</th>
            <th scope="col">Keluar paling lambat</th>
            <th scope="col">TP harian tersentuh</th>
            <th scope="col">Akurasi arah</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in candidates" :key="item.symbol">
            <td>
              <strong>{{ item.symbol }}</strong
              ><small>{{ item.name }}</small>
            </td>
            <td>
              <div>&gt; {{ rupiah.format(item.plan.stop) }}</div>
              <div>≤ {{ rupiah.format(item.plan.entry_limit) }}</div>
              <small>{{ item.plan.entry_time }} WIB · sesi 1</small>
            </td>
            <td class="up">{{ percent.format(item.probability) }}</td>
            <td>+{{ percent.format(item.change) }}</td>
            <td>
              {{ rupiah.format(item.tp) }} (+{{ percent.format(item.target) }})
              <small v-if="item.plan.tp_window">
                Historis: sesi {{ item.plan.tp_window.session }}, candle
                {{ item.plan.tp_window.start }} WIB
              </small>
              <small v-else>Data jam TP belum cukup</small>
              <small
                >{{ item.plan.hits }}/{{ item.plan.sample }} TP pada replay
                intraday</small
              >
            </td>
            <td>
              {{ rupiah.format(item.plan.stop) }} (−{{
                percent.format(item.plan.risk)
              }})
              <small
                >{{ item.plan.stops }}/{{ item.plan.sample }} kena stop pada
                replay</small
              >
            </td>
            <td>
              {{ item.plan.deadline }} WIB · sesi {{ horizon }}
              <small
                >{{ item.plan.timed_exits }}/{{ item.plan.sample }} keluar
                karena waktu</small
              >
            </td>
            <td>{{ percent.format(item.tp_hit) }} · {{ item.tp_n }} uji</td>
            <td>{{ percent.format(item.accuracy) }} · {{ item.test_n }} uji</td>
          </tr>
        </tbody>
      </table>
    </div>
    <AiAnalysis
      :context="aiContext"
      :load-universe="loadAiUniverse"
      :busy="!!pending"
    />
    <UiAccordion title="Cara membaca rencana dan hasil">
      <p>
        Sesi 1 adalah hari bursa pertama setelah tanggal acuan di atas. Rencana
        entry hanya berlaku saat pembukaan 09.00 WIB. Lewati jika pembukaan
        sudah lewat atau harga buka di luar batas entry. Setelah masuk, aturan
        jual adalah keluar ketika harga menyentuh TP atau stop-loss. Jika
        keduanya belum tersentuh, keluar pada 15.45 WIB di sesi terakhir
        horizon.
      </p>
      <p>
        Stop-loss memakai median rentang harga 20 sesi terakhir relatif terhadap
        harga acuan, dengan batas 1–10%. Jam TP historis memakai median candle
        dari minimal tiga kejadian TP pada replay 15 menit selama satu bulan,
        dengan level relatif yang sama. Jika TP dan stop tersentuh di candle
        yang sama dan harga buka di antara kedua level, replay mencatat stop
        lebih dulu. Angka ini menggambarkan riwayat. Harga aktual bisa melewati
        level saat gap, dan aplikasi tidak mengirim order.
      </p>
      <p>
        Harga acuan berasal dari penutupan terakhir. Estimasi membandingkan
        momentum harga saat ini dengan pola yang sama dalam riwayat dua tahun.
        Target TP memakai median kenaikan intrahorizon tertinggi dari pola
        tersebut. Harga TP adalah estimasi teoretis sebelum penyesuaian fraksi
        harga.
      </p>
      <p>
        Akurasi arah dan TP tersentuh dihitung dari backtest berjalan. Pada
        setiap sesi uji, model hanya memakai hasil yang sudah tersedia. TP
        tersentuh berarti harga tertinggi mencapai target simulasi. Angka ini
        mengabaikan biaya dan eksekusi order.
      </p>
      <p>
        Pemindaian memprioritaskan hingga 90 saham dari daftar BEI dengan
        kapitalisasi di atas Rp1 triliun dan volume rata-rata 3 bulan tertinggi.
        Riwayat harus lengkap untuk 20 sesi terakhir dengan median nilai
        transaksi perkiraan minimal Rp5 miliar per sesi. Hanya kandidat dengan
        estimasi peluang naik minimal 55%, proyeksi perubahan positif, minimal
        10 uji TP, dan skor Brier lebih baik dari peluang historis dasar yang
        ditampilkan.
      </p>
    </UiAccordion>
  </main>
</template>

<style>
:root {
  color-scheme: dark;
  font:
    16px system-ui,
    sans-serif;
  color: #ecf2f8;
  background: #101720;
  --line: #354553;
  --muted: #aebdcc;
  --accent: #a7e7cd;
}
* {
  box-sizing: border-box;
}
body {
  margin: 0;
}
main {
  max-width: 1210px;
  margin: auto;
  padding: clamp(28px, 6vw, 68px) clamp(16px, 4vw, 40px);
}
header {
  padding-bottom: 24px;
}
.brand {
  color: var(--muted);
  font-size: 0.82rem;
  font-weight: 600;
}
.brand span {
  color: var(--accent);
  margin: 0 0.3em;
}
h1 {
  font-size: clamp(2.2rem, 6vw, 4rem);
  letter-spacing: -0.06em;
  line-height: 1.04;
  margin: 12px 0;
}
p {
  color: var(--muted);
  line-height: 1.55;
}
header p {
  margin: 0;
}
.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 20px;
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #192430;
}
.search-form,
.search-field {
  min-width: 0;
}
.control-label {
  display: block;
  margin: 0 0 8px;
  color: #d5e0ea;
  font-size: 0.82rem;
  font-weight: 650;
}
.search-field {
  display: flex;
  gap: 8px;
  position: relative;
}
input[type="search"],
button {
  font: inherit;
  border: 1px solid var(--line);
  border-radius: 7px;
  padding: 10px 12px;
  min-height: 44px;
}
input[type="search"] {
  min-width: 0;
  flex: 1;
  color: inherit;
  background: #101720;
}
button {
  font-weight: 650;
  color: inherit;
  background: #243343;
  cursor: pointer;
}
button:disabled {
  opacity: 0.55;
  cursor: default;
}
button:not(:disabled):hover {
  filter: brightness(1.15);
}
.suggestions {
  position: absolute;
  z-index: 2;
  top: calc(100% + 6px);
  inset-inline: 0;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #202d3a;
  box-shadow: 0 12px 24px #0005;
}
.suggestions ul {
  margin: 0;
  padding: 4px;
  list-style: none;
}
.suggestions button {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(4em, auto) 1fr;
  gap: 10px;
  align-items: center;
  border: 0;
  text-align: left;
  background: transparent;
}
.suggestions button:hover,
.suggestions button:focus-visible {
  background: #2c3c4d;
}
.suggestions span {
  color: var(--muted);
  font-size: 0.9rem;
  overflow-wrap: anywhere;
}
.suggestions p {
  margin: 12px;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 12px;
}
fieldset {
  border: 0;
  margin: 0;
  padding: 0;
  min-width: 0;
}
.segments {
  display: flex;
  background: #101720;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 3px;
}
.segments label {
  position: relative;
  cursor: pointer;
}
.segments input {
  position: absolute;
  opacity: 0;
  width: 1px;
  height: 1px;
}
.segments span {
  display: grid;
  place-items: center;
  padding: 7px 12px;
  min-height: 36px;
  border-radius: 5px;
  white-space: nowrap;
  color: var(--muted);
}
.segments input:checked + span {
  background: #354e61;
  color: #fff;
  font-weight: 650;
}
.segments input:focus-visible + span {
  outline: 2px solid #ecce81;
  outline-offset: 1px;
}
.scan-button {
  background: var(--accent);
  color: #102822;
  border-color: transparent;
}
.result-status {
  margin: 20px 0 12px;
}
.stock-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 28px;
  align-items: center;
  padding: 16px 0;
  border-bottom: 1px solid var(--line);
}
.stock-summary h2,
.stock-summary p {
  margin: 0;
}
.stock-price strong {
  font-size: 1.25rem;
  font-variant-numeric: tabular-nums;
}
.back-button {
  margin-left: auto;
}
@media (max-width: 680px) {
  .workspace {
    grid-template-columns: minmax(0, 1fr);
    padding: 12px;
    gap: 16px;
  }
  .search-field {
    flex-wrap: wrap;
  }
  .suggestions {
    position: static;
    flex: 0 0 100%;
    box-shadow: none;
  }
  .actions {
    justify-content: space-between;
  }
  .back-button {
    margin-left: 0;
  }
}
:focus-visible {
  outline: 2px solid #ecce81;
  outline-offset: 3px;
}
.panel {
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #192430;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-variant-numeric: tabular-nums;
}
th,
td {
  padding: 14px;
  text-align: right;
  white-space: nowrap;
}
th {
  color: var(--muted);
  font-size: 0.8rem;
}
td {
  border-top: 1px solid var(--line);
}
th:first-child,
td:first-child {
  text-align: left;
}
small {
  display: block;
  color: var(--muted);
  white-space: normal;
}
.up {
  color: var(--accent);
  font-weight: 700;
}
</style>
