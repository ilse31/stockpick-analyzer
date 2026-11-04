import { computed, ref, shallowRef } from 'vue'
import { $fetch } from 'ofetch'
import type { AiContext, AiUniverse, Horizon, ScanResult, Stock, StockResult } from '../types/stock'
import { requestError } from './requestError'

export function useStockScreener() {
  const horizon = ref<Horizon>('1')
  const snapshot = shallowRef<ScanResult | null>(null)
  const stockResult = shallowRef<StockResult | null>(null)
  const directory = shallowRef<Stock[] | null>(null)
  const query = ref('')
  const showSuggestions = ref(false)
  const directoryLoading = ref(false)
  const directoryError = ref(false)
  const pending = ref<'' | 'scan' | 'search'>('')
  const errorMessage = ref('')

  const suggestions = computed(() => {
    const term = query.value.trim().toUpperCase()
    if (!term || !directory.value) return []
    const matches = directory.value.filter(({ symbol, name }) =>
      symbol.includes(term) || name.toUpperCase().includes(term))
    return matches.sort((a, b) => Number(b.symbol.startsWith(term)) - Number(a.symbol.startsWith(term)))
      .slice(0, 6)
  })

  const candidates = computed(() =>
    pending.value ? [] : (stockResult.value ?? snapshot.value)?.ranks[horizon.value] ?? [])
  const aiContext = computed<AiContext | null>(() => {
    const active = stockResult.value ?? snapshot.value
    if (!active || pending.value) return null
    return {
      date: active.date,
      horizon: horizon.value,
      stock: 'stock' in active ? active.stock : undefined,
      candidates: candidates.value.map(({ symbol, close, probability, change, tp, tp_hit, tp_n, accuracy, test_n, plan }) => ({
        symbol, close, probability, change, tp, tp_hit, tp_n, accuracy, test_n, plan,
      })),
    }
  })

  const status = computed(() => {
    if (pending.value === 'search') return 'Mengambil riwayat saham dan mengecek rencana trading.'
    if (pending.value === 'scan') return 'Mengambil data dan menjalankan backtest. Pemindaian pertama bisa memakan waktu.'
    if (errorMessage.value) return errorMessage.value
    if (stockResult.value) {
      const { date, status } = stockResult.value
      if (candidates.value.length) return `Rencana ${horizon.value} sesi · Acuan ${date}`
      return status === 'skipped'
        ? 'Data historis atau likuiditas belum memenuhi kriteria rencana trading.'
        : `Belum ada sinyal beli yang lolos untuk ${horizon.value} sesi.`
    }
    if (!snapshot.value) return 'Mulai pemindaian untuk mengambil data IDX.'

    const { date, counts, selected, quoted, listed } = snapshot.value
    const { analyzed, skipped, failed } = counts
    let headline = 'Belum ada kandidat yang lolos'
    if (analyzed === 0) headline = 'Data belum cukup untuk analisis'
    else if (candidates.value.length) headline = `${candidates.value.length} kandidat`

    return `${headline} untuk ${horizon.value} sesi. Sesi ${date} · ${analyzed}/${selected} dianalisis · ${skipped} tersaring · ${failed} gagal · ${quoted}/${listed} cakupan kuotasi.`
  })

  async function openSuggestions() {
    showSuggestions.value = true
    if (directory.value || directoryLoading.value) return
    directoryLoading.value = true
    directoryError.value = false
    try {
      directory.value = await $fetch<Stock[]>('/api/stocks')
    } catch {
      directoryError.value = true
    } finally {
      directoryLoading.value = false
    }
  }

  function closeSuggestions() {
    showSuggestions.value = false
  }

  function onSearchBlur(event: FocusEvent) {
    if (!(event.currentTarget instanceof Node && event.relatedTarget instanceof Node
        && event.currentTarget.contains(event.relatedTarget))) closeSuggestions()
  }

  async function search(symbol?: string) {
    if (pending.value) return
    const term = query.value.trim().toUpperCase()
    const match = symbol ?? directory.value?.find(stock => stock.symbol === term)?.symbol
      ?? (suggestions.value.length === 1 ? suggestions.value[0]?.symbol : null)
    if (!match && (suggestions.value.length > 1 || !/^[A-Z0-9]{1,12}$/.test(term))) {
      showSuggestions.value = true
      return
    }

    query.value = match ?? term
    closeSuggestions()
    pending.value = 'search'
    stockResult.value = null
    errorMessage.value = ''
    try {
      stockResult.value = await $fetch<StockResult>('/api/stock', { query: { symbol: query.value } })
    } catch (error) {
      errorMessage.value = requestError(error, 'Pencarian gagal. Coba lagi.')
    } finally {
      pending.value = ''
    }
  }

  function showScreener() {
    stockResult.value = null
    errorMessage.value = ''
  }

  async function loadAiUniverse(): Promise<AiUniverse> {
    const selected = horizon.value
    if (pending.value) throw new Error('Tunggu pemindaian atau pencarian yang sedang berjalan.')
    if (!snapshot.value) await scan()
    const current = snapshot.value
    const stocks = current?.universe?.[selected]
    if (!current || !stocks?.length) throw new Error(errorMessage.value || 'Belum ada saham dengan data cukup untuk horizon ini.')
    return { date: current.date, horizon: selected, stocks }
  }

  async function scan() {
    closeSuggestions()
    pending.value = 'scan'
    stockResult.value = null
    errorMessage.value = ''
    try {
      snapshot.value = await $fetch<ScanResult>('/api/scan', { method: 'POST' })
    } catch (error) {
      errorMessage.value = requestError(error, 'Pemindaian gagal. Coba lagi.')
    } finally {
      pending.value = ''
    }
  }

  return {
    horizon, stockResult, query, showSuggestions, directoryLoading, directoryError,
    suggestions, candidates, aiContext, status, pending,
    openSuggestions, closeSuggestions, onSearchBlur, search, showScreener, loadAiUniverse, scan,
  }
}
