<template>
  <Teleport to="body">
    <div class="duplicate-backdrop erp-dialog-backdrop" @click.self="!busy && emit('close')">
      <section
        v-erp-dialog
        class="erp-dialog erp-dialog--lg duplicate-dialog"
        :aria-label="uiText(addressesOnly ? 'Conferir endereços' : 'Conferir duplicidades')"
      >
        <header class="erp-dialog__header">
          <h2>{{ uiText(addressesOnly ? 'Conferir endereços' : 'Conferir duplicidades') }}</h2>
          <button
            data-dialog-close
            class="erp-button erp-button--ghost erp-button--icon"
            :disabled="busy"
            :aria-label="uiText('Fechar')"
            @click="emit('close')"
          >
            ×
          </button>
        </header>
        <main class="erp-dialog__body">
          <p class="hint">
            {{
              uiText(
                'Confira a pessoa e o local antes de unir. O cadastro principal permanece visível; históricos e referências antigas são preservados.',
              )
            }}
          </p>
          <div v-if="!selected" class="review-filters">
            <ErpDropdown
              v-if="!addressesOnly"
              v-model="kind"
              :disabled="busy"
              :label="uiText('Tipo de cadastro')"
              :options="[
                { value: 'customers', label: uiText('Clientes') },
                { value: 'addresses', label: uiText('Endereços') },
              ]"
            /><label
              >{{ uiText('Buscar por nome')
              }}<input
                v-model="search"
                :disabled="busy"
                maxlength="100"
                @keydown.enter="load" /></label
            ><button class="erp-button erp-button--secondary" :disabled="busy" @click="load">
              {{ uiText('Buscar duplicidades') }}
            </button>
          </div>
          <p v-if="error" role="alert" class="error">{{ uiText(error) }}</p>
          <p v-if="notice" role="status">{{ uiText(notice) }}</p>
          <p v-if="busy" role="status">{{ uiText('Conferindo...') }}</p>
          <template v-if="selected">
            <div class="pair">
              <article>
                <h3>{{ uiText('Cadastro principal') }}</h3>
                <strong>{{ selected.target.name }}</strong>
                <p>{{ selected.target.details || '—' }}</p>
                <code>{{ selected.target.id }}</code>
              </article>
              <article>
                <h3>{{ uiText('Cadastro duplicado') }}</h3>
                <strong>{{ selected.source.name }}</strong>
                <p>{{ selected.source.details || '—' }}</p>
                <code>{{ selected.source.id }}</code>
              </article>
            </div>
            <button
              class="erp-button erp-button--secondary erp-button--sm"
              :disabled="busy"
              @click="swap"
            >
              {{ uiText('Inverter principal') }}
            </button>
            <template v-if="plan">
              <p v-if="plan.conflicting_fields?.length" class="error">
                {{
                  uiText(
                    'Dados divergentes impedem a união. Corrija os cadastros e confira novamente.',
                  )
                }}
                {{ plan.conflicting_fields.join(', ') }}
              </p>
              <p v-else>
                {{ uiText('Vínculos a reunir no principal') }}:
                {{
                  Object.entries(plan.links_to_move || {})
                    .map(([key, value]) => `${linkLabel(key)}: ${value}`)
                    .join(' · ') || uiText('Histórico do endereço por referência')
                }}
              </p>
              <label v-if="plan.state === 'ready'" class="review-check"
                ><input v-model="confirmed" type="checkbox" :disabled="busy" />{{
                  uiText(
                    'Conferi a identidade, os dados e o cadastro principal. Quero unir este par.',
                  )
                }}</label
              >
            </template>
          </template>
          <template v-else-if="loaded && !busy">
            <p v-if="incomplete" class="hint">
              {{
                uiText(
                  'Revisão parcial: refine a busca ou una os pares conferidos e busque novamente. São mostrados até 25 pares por consulta.',
                )
              }}
            </p>
            <p v-if="!rows.length">
              {{
                uiText(
                  'Nenhuma duplicidade reconhecida nesta consulta. Isso não comprova que todos os cadastros são únicos.',
                )
              }}
            </p>
            <article
              v-for="(row, index) in rows"
              :key="row.target.id + row.source.id"
              class="candidate"
            >
              <div>
                <strong>{{ row.target.name }} / {{ row.source.name }}</strong>
                <p>{{ row.target.details || '—' }}</p>
                <p>{{ row.source.details || '—' }}</p>
              </div>
              <button
                class="erp-button erp-button--secondary erp-button--sm"
                @click="select(index)"
              >
                {{ uiText('Conferir par') }}
              </button>
            </article>
          </template>
        </main>
        <footer class="erp-dialog__footer">
          <button
            class="erp-button erp-button--secondary"
            :disabled="busy"
            @click="selected ? back() : emit('close')"
          >
            {{ uiText(selected ? 'Voltar' : 'Fechar') }}</button
          ><button
            v-if="selected && !plan"
            class="erp-button erp-button--primary"
            :disabled="busy"
            @click="preview"
          >
            {{ uiText('Revisar união') }}</button
          ><button
            v-if="selected && plan?.state === 'ready'"
            class="erp-button erp-button--primary"
            :disabled="busy || !confirmed"
            @click="apply"
          >
            {{ uiText('Unir cadastros conferidos') }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>
<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import api from '@/services/api'
import { uiText } from '@/i18n/uiText'
import { vErpDialog } from '@/directives/erpDialog'
import ErpDropdown from '@/components/ui/ErpDropdown.vue'
type Kind = 'customers' | 'addresses'
interface RecordInfo {
  id: string
  name: string
  details: string
}
interface Pair {
  target: RecordInfo
  source: RecordInfo
}
interface Plan {
  state: string
  plan_token?: string
  conflicting_fields?: string[]
  links_to_move?: Record<string, number>
}
const props = withDefaults(defineProps<{ initialKind?: Kind; addressesOnly?: boolean }>(), { initialKind: 'customers', addressesOnly: false })
const emit = defineEmits<{ close: []; changed: [] }>()
const kind = ref<Kind>(props.addressesOnly ? 'addresses' : props.initialKind),
  search = ref(''),
  rows = ref<Pair[]>([]),
  selected = ref<Pair | null>(null),
  plan = ref<Plan | null>(null)
const busy = ref(false),
  error = ref(''),
  notice = ref(''),
  loaded = ref(false),
  incomplete = ref(false),
  confirmed = ref(false)
const linkLabel = (key: string) =>
  uiText(
    (
      {
        orders: 'Pedidos',
        tracking: 'Rastreios',
        addresses: 'Endereços',
        pdv_customers: 'Clientes PDV',
      } as Record<string, string>
    )[key] || key,
  )
function failure(e: unknown) {
  const detail = (e as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  error.value =
    typeof detail === 'string'
      ? detail
      : 'Não foi possível concluir. Confira a conexão e tente novamente.'
}
function body() {
  return {
    kind: kind.value,
    target_id: selected.value!.target.id,
    source_id: selected.value!.source.id,
  }
}
async function load() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  loaded.value = false
  try {
    const { data } = await api.get<{ items: Pair[]; incomplete: boolean }>(
      '/api/clientes/maintenance/duplicates',
      { params: { kind: kind.value, q: search.value } },
    )
    rows.value = data.items
    incomplete.value = data.incomplete
    loaded.value = true
  } catch (e) {
    failure(e)
  } finally {
    busy.value = false
  }
}
function select(index: number) {
  selected.value = rows.value[index]
  plan.value = null
  confirmed.value = false
  error.value = ''
  notice.value = ''
}
function swap() {
  if (!selected.value) return
  selected.value = { target: selected.value.source, source: selected.value.target }
  plan.value = null
  confirmed.value = false
  error.value = ''
}
function back() {
  selected.value = null
  plan.value = null
  confirmed.value = false
  error.value = ''
}
async function preview() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  confirmed.value = false
  try {
    plan.value = (await api.post<Plan>('/api/clientes/maintenance/duplicates/preview', body())).data
    if (plan.value.state === 'already_merged') {
      emit('changed')
      back()
      notice.value = 'Cadastros unidos. Históricos preservados.'
    }
  } catch (e) {
    failure(e)
  } finally {
    busy.value = false
  }
  if (notice.value && !selected.value && !error.value) await load()
}
async function apply() {
  if (busy.value || !confirmed.value || !plan.value?.plan_token) return
  busy.value = true
  error.value = ''
  try {
    await api.post('/api/clientes/maintenance/duplicates/confirm', {
      ...body(),
      plan_token: plan.value.plan_token,
      confirm: true,
    })
    emit('changed')
    back()
    notice.value = 'Cadastros unidos. Históricos preservados.'
  } catch (e) {
    failure(e)
    plan.value = null
    confirmed.value = false
  } finally {
    busy.value = false
  }
  if (!error.value) await load()
}
watch(kind, () => {
  back()
  notice.value = ''
  void load()
})
onMounted(load)
</script>
<style scoped>
.duplicate-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2500;
  display: flex;
  align-items: center;
  justify-content: center;
}
.duplicate-dialog {
  width: min(760px, 100%);
}
h2 {
  margin: 0;
  font-size: 18px;
}
.hint {
  font-size: 13px;
  color: #64748b;
  line-height: 1.6;
}
.review-filters {
  display: flex;
  align-items: end;
  gap: 10px;
  flex-wrap: wrap;
}
.review-filters > * {
  flex: 1;
  min-width: 180px;
}
.review-filters label {
  display: grid;
  gap: 6px;
  font-size: 13px;
}
input:not([type='checkbox']) {
  min-width: 0;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 10px;
  font: inherit;
}
.candidate {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: space-between;
  border: 1px solid #dbe3ef;
  border-radius: 10px;
  padding: 12px;
  margin-top: 12px;
}
.candidate p,
.pair p {
  font-size: 12px;
  color: #475569;
  overflow-wrap: anywhere;
}
.pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin: 16px 0;
}
.pair article {
  min-width: 0;
  border: 1px solid #dbe3ef;
  border-radius: 10px;
  padding: 12px;
}
.pair h3 {
  font-size: 13px;
  color: #2563eb;
}
.pair code {
  font-size: 10px;
  overflow-wrap: anywhere;
}
.review-check {
  display: flex;
  align-items: start;
  gap: 8px;
  font-size: 14px;
  line-height: 1.5;
  margin: 20px 0;
}
.error {
  color: #b91c1c;
  font-size: 13px;
}
@media (max-width: 600px) {
  .pair {
    grid-template-columns: 1fr;
  }
  .candidate {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
