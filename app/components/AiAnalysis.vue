<script setup lang="ts">
import { ref, shallowRef } from 'vue'
import { $fetch } from 'ofetch'
import { requestError } from '../lib/requestError'
import type { AiContext, AiUniverse } from '../types/stock'

type AiAction = 'models' | 'analyze' | 'rank'
type Pick = { symbol: string; reason: string }
type AiResponse = { models: string[] } | { picks: Pick[] } | { text: string }
type AiResult =
  | { kind: 'rank'; picks: (Pick & { qualified: boolean })[]; model: string; context: AiUniverse }
  | { kind: 'analyze'; text: string; model: string; context?: AiContext | null }

const props = defineProps<{
  context?: AiContext | null
  loadUniverse: () => Promise<AiUniverse>
  busy?: boolean
}>()

const baseUrl = ref('')
const apiKey = ref('')
const models = ref<string[]>([])
const model = ref('')
const question = ref('Jelaskan hasil screener, kriteria entry, dan risiko utamanya.')
const pending = ref<AiAction | ''>('')
const errorMessage = ref('')
const result = shallowRef<AiResult | null>(null)

function resetModels() {
  models.value = []
  model.value = ''
  result.value = null
  errorMessage.value = ''
}

async function callAi(action: AiAction) {
  if (pending.value) return
  pending.value = action
  errorMessage.value = ''
  result.value = null
  if (action === 'models') resetModels()

  const selectedModel = model.value
  try {
    const universe = action === 'rank' ? await props.loadUniverse() : null
    const context = props.context
    const data = await $fetch<AiResponse>('/api/ai', {
      method: 'POST',
      body: {
        action, baseUrl: baseUrl.value.trim(), apiKey: apiKey.value,
        model: selectedModel,
        question: action === 'rank' ? 'Pindai semua saham dalam data dan urutkan kandidat untuk horizon ini.' : question.value.trim(),
        context: action !== 'models' && (universe ?? context) ? JSON.stringify(universe ?? context) : '',
      },
    })
    if (action === 'models' && 'models' in data) {
      models.value = data.models
      if (!models.value.length) errorMessage.value = 'Penyedia tidak mengembalikan model.'
    } else if (universe && 'picks' in data) {
      const stocks = new Map(universe.stocks.map(stock => [stock.symbol, stock]))
      const picks = data.picks.map(pick => ({ ...pick, qualified: stocks.get(pick.symbol)?.qualified ?? false }))
      result.value = { kind: 'rank', picks, model: selectedModel, context: universe }
    } else if (action === 'analyze' && 'text' in data) {
      result.value = { kind: 'analyze', text: data.text, model: selectedModel, context }
    } else {
      throw new Error('Format respons AI tidak sesuai.')
    }
  } catch (error) {
    errorMessage.value = requestError(error, 'Permintaan AI gagal. Coba lagi.', true)
  } finally {
    pending.value = ''
  }
}
</script>

<template>
  <UiAccordion title="Analisis AI opsional">
    <p class="intro">Hubungkan penyedia yang kompatibel dengan OpenAI. Key hanya aktif selama halaman ini terbuka.</p>
    <form class="ai-form" @submit.prevent="callAi('analyze')">
      <label>
        URL dasar API
        <input v-model="baseUrl" type="url" placeholder="https://api.openai.com/v1"
          autocomplete="off" :disabled="!!pending" required
          @input="apiKey = ''; resetModels()">
      </label>
      <label>
        API key <small>(jika diperlukan)</small>
        <input v-model="apiKey" type="password" autocomplete="off"
          :disabled="!!pending" @input="resetModels()">
      </label>
      <div class="model-row">
        <div class="model-field">
          <label for="ai-model">Model</label>
          <select id="ai-model" v-model="model" :disabled="!!pending || !models.length" required>
            <option value="" disabled>Pilih model</option>
            <option v-for="id in models" :key="id" :value="id">{{ id }}</option>
          </select>
        </div>
        <button type="button" :disabled="!!pending || !baseUrl.trim()" @click="callAi('models')">
          {{ pending === 'models' ? 'Memuat…' : 'Muat model' }}
        </button>
      </div>
      <div class="scan-ai">
        <button type="button" :disabled="!!pending || busy || !model" @click="callAi('rank')">
          {{ pending === 'rank' ? 'Memindai dengan AI…' : 'Pindai dengan AI' }}
        </button>
        <p class="context">Peringkat AI mencakup saham dengan data cukup pada horizon yang dipilih. Jika belum ada hasil pindai, aplikasi mengambil data IDX terlebih dahulu.</p>
      </div>
      <label>
        Pertanyaan
        <textarea v-model="question" rows="3" maxlength="2000" :disabled="!!pending" required />
      </label>
      <p class="context">
        {{ context ? `Permintaan menyertakan hasil ${context.stock?.symbol ?? 'screener'} untuk ${context.horizon} sesi.` :
          'Belum ada hasil IDX yang akan disertakan.' }}
      </p>
      <button type="submit" :disabled="!!pending || !model || !question.trim()">
        {{ pending === 'analyze' ? 'Menganalisis…' : 'Tanya AI' }}
      </button>
    </form>
    <p v-if="errorMessage" role="alert">{{ errorMessage }}</p>
    <section v-if="result" class="ai-result" aria-label="Jawaban AI" aria-live="polite">
      <small>{{ result.model }}<template v-if="result.context"> · {{ result.context.horizon }} sesi · {{ result.context.date }}</template></small>
      <template v-if="result.kind === 'rank'">
        <h3>Peringkat AI</h3>
        <p>{{ result.context.stocks.length }} saham dievaluasi. Status filter lokal ditampilkan terpisah.</p>
        <ol v-if="result.picks.length">
          <li v-for="pick in result.picks" :key="pick.symbol">
            <strong>{{ pick.symbol }}</strong>
            <small>{{ pick.qualified ? 'Lolos filter lokal' : 'Belum lolos filter lokal' }}</small>
            <p>{{ pick.reason }}</p>
          </li>
        </ol>
        <p v-else>AI tidak memilih kandidat dari data ini.</p>
      </template>
      <p v-else>{{ result.text }}</p>
    </section>
  </UiAccordion>
</template>

<style scoped>
.intro { margin-bottom: 16px; }
.ai-form { display: grid; gap: 12px; max-width: 640px; }
label { display: grid; gap: 6px; min-width: 0; font-size: .88rem; font-weight: 650; }
label small { display: inline; }
input, select, textarea {
  width: 100%;
  min-height: 44px;
  padding: 10px 12px;
  color: inherit;
  font: inherit;
  background: #101720;
  border: 1px solid var(--line);
  border-radius: 7px;
}
textarea { resize: vertical; }
.model-field { min-width: 0; display: grid; gap: 6px; }
.model-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: end; }
.scan-ai { display: grid; gap: 8px; justify-items: start; }
.ai-result li + li { margin-top: 12px; }
.ai-result li p { margin: 4px 0; }
.context { margin: 0; font-size: .88rem; }
.ai-form > button { justify-self: start; }
.ai-result { margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--line); }
.ai-result p { white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
