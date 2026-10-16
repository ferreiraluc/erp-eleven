<template>
  <div class="erp-dialog-backdrop" @click.self="!busy && emit('close')">
    <section
      v-erp-dialog
      class="erp-dialog receiving-modal"
      role="dialog"
      aria-modal="true"
      :aria-label="tr('Lotes de recebimento')"
    >
      <header class="erp-dialog__header">
        <h2>{{ tr('Lotes de recebimento') }}</h2>
        <button
          data-dialog-close
          type="button"
          class="erp-button erp-button--secondary erp-button--icon"
          :disabled="busy"
          :aria-label="tr('Fechar')"
          @click="emit('close')"
        >
          ×
        </button>
      </header>
      <div class="erp-dialog__body">
        <p class="receiving-hint">
          {{
            tr(
              'Organize chegadas por data de cadastro ou seleção. Vincular a um lote não altera o estoque nem a grade do produto.',
            )
          }}
        </p>
        <p v-if="error" role="alert" class="receiving-error">{{ error }}</p>
        <p v-if="busy" role="status">{{ tr('Carregando...') }}</p>
        <template v-if="view === 'list'">
          <p v-if="selection?.length">
            {{ tr('{count} produtos selecionados', { count: selection.length }) }}
          </p>
          <div class="receiving-toolbar">
            <button
              v-if="canManage"
              type="button"
              class="erp-button erp-button--primary erp-button--sm"
              :disabled="busy"
              @click="start()"
            >
              + {{ tr('Novo lote') }}</button
            ><button
              type="button"
              class="erp-button erp-button--secondary erp-button--sm"
              :disabled="busy"
              @click="loadLots"
            >
              {{ tr('Atualizar') }}
            </button>
          </div>
          <p v-if="!lots.length && !busy">{{ tr('Nenhum lote cadastrado.') }}</p>
          <article v-for="lot in lots" :key="lot.id" class="receiving-lot">
            <div>
              <strong>{{ lot.name }}</strong
              ><small
                >{{ lot.received_on.split('-').reverse().join('/') }} ·
                {{ tr('{count} produtos vinculados', { count: lot.item_count }) }}</small
              >
              <p v-if="lot.notes">{{ lot.notes }}</p>
            </div>
            <div class="receiving-toolbar">
              <button
                v-if="selection?.length && canManage"
                type="button"
                class="erp-button erp-button--secondary erp-button--sm"
                :disabled="busy"
                @click="start(lot)"
              >
                {{ tr('Vincular seleção') }}</button
              ><button
                type="button"
                class="erp-button erp-button--secondary erp-button--sm"
                :disabled="busy"
                @click="openLot(lot)"
              >
                {{ tr('Conferir') }}</button
              ><button
                type="button"
                class="erp-button erp-button--primary erp-button--sm"
                @click="emit('filter', lot)"
              >
                {{ tr('Ver no estoque') }}
              </button>
            </div>
          </article>
          <div class="receiving-toolbar">
            <button
              type="button"
              class="erp-button erp-button--secondary erp-button--sm"
              :disabled="busy || page === 1"
              @click="changePage(-1)"
            >
              ←</button
            ><span>{{ page }} / {{ Math.max(1, Math.ceil(total / 30)) }}</span
            ><button
              type="button"
              class="erp-button erp-button--secondary erp-button--sm"
              :disabled="busy || page * 30 >= total"
              @click="changePage(1)"
            >
              →
            </button>
          </div>
        </template>
        <template v-else-if="view === 'form'">
          <fieldset :disabled="busy || uncertain">
            <template v-if="!attachTo">
              <label
                >{{ tr('Nome do lote')
                }}<input
                  v-model="form.name"
                  maxlength="160"
                  :placeholder="tr('Ex: Leva 1 do container')"
              /></label>
              <div class="receiving-fields">
                <label
                  >{{ tr('Data de recebimento')
                  }}<input v-model="form.received_on" type="date" /></label
                ><label
                  >{{ tr('Descrição')
                  }}<textarea
                    v-model="form.notes"
                    maxlength="2000"
                    rows="2"
                    :placeholder="tr('Ex: 1ª leva recebida em 15/10')"
                  />
                </label>
              </div>
            </template>
            <strong v-else>{{ tr('Adicionar ao lote') }}: {{ attachTo.name }}</strong>
            <ErpDropdown
              v-model="selectionSource"
              :options="selectionOptions"
              :label="tr('Selecionar produtos por')"
            />
            <div v-if="selectionSource === 'dates'" class="receiving-fields">
              <label>{{ tr('Cadastro de') }}<input v-model="dateFrom" type="date" /></label
              ><label>{{ tr('Até') }}<input v-model="dateTo" type="date" /></label
              ><button
                type="button"
                class="erp-button erp-button--secondary"
                @click="findCandidates"
              >
                {{ tr('Buscar produtos') }}
              </button>
            </div>
            <small>{{
              tr(
                'Datas seguem o horário de Brasília. A seleção considera todos os cadastros do período, incluindo inativos, até 1000 produtos por vez.',
              )
            }}</small>
            <p v-if="candidates.length">
              <strong>{{ tr('{count} produtos selecionados', { count: selected.length }) }}</strong>
              / {{ candidates.length }}
              <button
                type="button"
                class="erp-button erp-button--ghost erp-button--sm"
                @click="
                  selected =
                    selected.length === candidates.length ? [] : candidates.map((row) => row.id)
                "
              >
                {{ tr(selected.length === candidates.length ? 'Limpar' : 'Selecionar todos') }}
              </button>
            </p>
            <div class="receiving-products">
              <label v-for="row in candidatePage" :key="row.id" class="receiving-product"
                ><input v-model="selected" type="checkbox" :value="row.id" /><span
                  ><strong>{{ row.name }}</strong
                  ><small>{{ [row.size, row.color].filter(Boolean).join(' · ') }}</small></span
                ></label
              >
            </div>
            <div v-if="candidates.length > 50" class="receiving-toolbar">
              <button
                type="button"
                class="erp-button erp-button--secondary erp-button--sm"
                :disabled="candidateOffset === 0"
                @click="candidateOffset -= 50"
              >
                ←</button
              ><span
                >{{ candidateOffset + 1 }}–{{ Math.min(candidateOffset + 50, candidates.length) }} /
                {{ candidates.length }}</span
              ><button
                type="button"
                class="erp-button erp-button--secondary erp-button--sm"
                :disabled="candidateOffset + 50 >= candidates.length"
                @click="candidateOffset += 50"
              >
                →
              </button>
            </div>
          </fieldset>
          <p v-if="uncertain" role="status">
            {{
              tr(
                'A resposta não chegou. Tente confirmar a mesma operação novamente; os vínculos não serão duplicados.',
              )
            }}
          </p>
        </template>
        <template v-else-if="current">
          <fieldset :disabled="busy || !canManage">
            <label>{{ tr('Nome do lote') }}<input v-model="form.name" maxlength="160" /></label
            ><label
              >{{ tr('Data de recebimento')
              }}<input v-model="form.received_on" type="date" /></label
            ><label
              >{{ tr('Descrição') }}<textarea v-model="form.notes" maxlength="2000" rows="2" />
            </label>
          </fieldset>
          <div class="receiving-toolbar">
            <button
              v-if="canManage"
              type="button"
              class="erp-button erp-button--primary erp-button--sm"
              :disabled="busy || form.name.trim().length < 2 || !form.received_on"
              @click="edit"
            >
              {{ tr('Salvar') }}</button
            ><button
              v-if="canManage"
              type="button"
              class="erp-button erp-button--secondary erp-button--sm"
              :disabled="busy"
              @click="start(current)"
            >
              {{ tr('Adicionar produtos') }}</button
            ><button
              type="button"
              class="erp-button erp-button--secondary erp-button--sm"
              @click="emit('filter', current)"
            >
              {{ tr('Ver no estoque') }}
            </button>
          </div>
          <p>{{ tr('{count} produtos vinculados', { count: current.item_count }) }}</p>
          <div class="receiving-products">
            <div v-for="row in members" :key="row.id" class="receiving-product">
              <span
                ><strong>{{ row.name }}</strong
                ><small>{{
                  row.deleted
                    ? tr('Produto excluído — histórico preservado')
                    : [row.size, row.color].filter(Boolean).join(' · ')
                }}</small></span
              ><button
                v-if="canManage"
                type="button"
                class="erp-button erp-button--ghost erp-button--sm"
                :disabled="busy"
                :aria-label="tr('Retirar {name} do lote', { name: row.name })"
                @click="remove(row)"
              >
                {{ tr('Retirar do lote') }}
              </button>
            </div>
          </div>
          <div class="receiving-toolbar">
            <button
              type="button"
              class="erp-button erp-button--secondary erp-button--sm"
              :disabled="busy || memberPage === 1"
              @click="changeMemberPage(-1)"
            >
              ←</button
            ><span>{{ memberPage }} / {{ Math.max(1, Math.ceil(current.item_count / 50)) }}</span
            ><button
              type="button"
              class="erp-button erp-button--secondary erp-button--sm"
              :disabled="busy || memberPage * 50 >= current.item_count"
              @click="changeMemberPage(1)"
            >
              →
            </button>
          </div>
        </template>
      </div>
      <footer class="erp-dialog__footer">
        <label v-if="view === 'form'" class="receiving-confirm"
          ><input v-model="confirmed" type="checkbox" :disabled="busy || uncertain" />{{
            tr('Conferi os produtos que serão vinculados a este lote.')
          }}</label
        ><button
          v-if="view !== 'list'"
          type="button"
          class="erp-button erp-button--secondary"
          :disabled="busy"
          @click="showList"
        >
          {{ tr('Voltar') }}</button
        ><button
          type="button"
          class="erp-button erp-button--secondary"
          :disabled="busy"
          @click="emit('close')"
        >
          {{ tr('Fechar') }}</button
        ><button
          v-if="view === 'form'"
          type="button"
          class="erp-button erp-button--primary"
          :disabled="
            busy ||
            (!uncertain &&
              (!confirmed ||
                !selected.length ||
                (!attachTo && (form.name.trim().length < 2 || !form.received_on))))
          "
          @click="save"
        >
          {{ tr(uncertain ? 'Conferir resultado' : attachTo ? 'Vincular produtos' : 'Criar lote') }}
        </button>
      </footer>
    </section>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import { vErpDialog } from '@/directives/erpDialog'
import ErpDropdown from '@/components/ui/ErpDropdown.vue'
import {
  receivingAPI,
  type ReceivingLot,
  type ReceivingCandidate,
  type ReceivingMember,
} from '@/services/inventoryReceiving'
import { useInventoryI18n } from './i18n'
const props = defineProps<{ selection?: ReceivingCandidate[]; canManage: boolean }>()
const emit = defineEmits<{ close: []; filter: [lot: ReceivingLot] }>()
const { tr } = useInventoryI18n()
const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Sao_Paulo' }).format(new Date())
const view = ref<'list' | 'form' | 'detail'>('list'),
  busy = ref(false),
  error = ref(''),
  uncertain = ref(false),
  confirmed = ref(false)
const lots = ref<ReceivingLot[]>([]),
  total = ref(0),
  page = ref(1),
  current = ref<ReceivingLot>(),
  members = ref<ReceivingMember[]>([]),
  memberPage = ref(1)
const attachTo = ref<ReceivingLot>(),
  selectionSource = ref('dates'),
  dateFrom = ref(today),
  dateTo = ref(today)
const candidates = ref<ReceivingCandidate[]>([]),
  selected = ref<string[]>([]),
  candidateOffset = ref(0)
const candidatePage = computed(() =>
  candidates.value.slice(candidateOffset.value, candidateOffset.value + 50),
)
const selectionOptions = computed(() => [
  { value: 'dates', label: tr('Data do cadastro') },
  ...(props.selection?.length ? [{ value: 'manual', label: tr('Seleção manual do estoque') }] : []),
])
const form = reactive({ name: '', notes: '', received_on: today })
let requestId = crypto.randomUUID()
async function run(work: () => Promise<void>) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await work()
  } catch (e) {
    error.value =
      isAxiosError(e) && typeof e.response?.data?.detail === 'string'
        ? tr(e.response.data.detail)
        : tr('Não foi possível concluir. Tente novamente.')
  } finally {
    busy.value = false
  }
}
async function loadLots() {
  await run(async () => {
    const data = await receivingAPI.list(page.value)
    lots.value = data.items
    total.value = data.total
  })
}
function sourceChanged() {
  candidates.value = selectionSource.value === 'manual' ? [...(props.selection || [])] : []
  selected.value = candidates.value.map((r) => r.id)
  candidateOffset.value = 0
}
function start(lot?: ReceivingLot) {
  attachTo.value = lot
  form.name = ''
  form.notes = ''
  form.received_on = today
  requestId = crypto.randomUUID()
  uncertain.value = false
  error.value = ''
  selectionSource.value = props.selection?.length ? 'manual' : 'dates'
  sourceChanged()
  confirmed.value = false
  view.value = 'form'
}
watch(selectionSource, sourceChanged)
watch([dateFrom, dateTo], () => {
  if (selectionSource.value === 'dates') {
    candidates.value = []
    selected.value = []
    candidateOffset.value = 0
  }
})
watch(
  [form, selected],
  () => {
    confirmed.value = false
  },
  { deep: true },
)
async function findCandidates() {
  await run(async () => {
    const data = await receivingAPI.candidates(dateFrom.value, dateTo.value)
    candidates.value = data.items
    selected.value = data.items.map((r) => r.id)
    candidateOffset.value = 0
  })
}
async function save() {
  await run(async () => {
    try {
      const result = attachTo.value
        ? await receivingAPI.attach(attachTo.value.id, selected.value)
        : await receivingAPI.create({
            ...form,
            request_id: requestId,
            item_ids: [...selected.value],
            confirm: true,
          })
      uncertain.value = false
      current.value = result
      memberPage.value = 1
      const data = await receivingAPI.members(result.id)
      members.value = data.items
      view.value = 'detail'
      Object.assign(form, {
        name: result.name,
        notes: result.notes,
        received_on: result.received_on,
      })
    } catch (e) {
      uncertain.value = !isAxiosError(e) || !e.response || e.response.status >= 500
      throw e
    }
  })
}
async function openLot(lot: ReceivingLot) {
  current.value = lot
  Object.assign(form, { name: lot.name, notes: lot.notes, received_on: lot.received_on })
  memberPage.value = 1
  view.value = 'detail'
  await loadMembers()
}
async function loadMembers() {
  await run(async () => {
    if (!current.value) return
    const data = await receivingAPI.members(current.value.id, memberPage.value)
    current.value = data.lot
    members.value = data.items
  })
}
async function edit() {
  await run(async () => {
    if (current.value)
      current.value = await receivingAPI.edit(current.value.id, {
        name: form.name,
        notes: form.notes,
        received_on: form.received_on,
      })
  })
}
async function remove(row: ReceivingMember) {
  await run(async () => {
    if (!current.value) return
    await receivingAPI.detach(current.value.id, row.id)
    const data = await receivingAPI.members(current.value.id, memberPage.value)
    current.value = data.lot
    members.value = data.items
  })
}
function changePage(delta: number) {
  page.value += delta
  void loadLots()
}
function changeMemberPage(delta: number) {
  memberPage.value += delta
  void loadMembers()
}
function showList() {
  view.value = 'list'
  void loadLots()
}
onMounted(loadLots)
</script>
<style scoped>
.erp-dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
}
.receiving-modal {
  --dialog-width: 760px;
}
h2 {
  font-size: 1.15rem;
  margin: 0;
}
.receiving-hint,
small {
  font-size: 0.8rem;
  color: #64748b;
  line-height: 1.5;
}
small {
  display: block;
}
.receiving-error {
  color: #b91c1c;
}
.receiving-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin: 12px 0;
}
.receiving-lot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px;
  margin-top: 10px;
}
.receiving-lot p {
  margin: 5px 0;
  font-size: 0.85rem;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.receiving-lot > div {
  min-width: 0;
}
fieldset {
  border: 0;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 12px;
  min-width: 0;
}
label {
  display: grid;
  gap: 5px;
  font-size: 0.85rem;
  font-weight: 600;
}
input:not([type='checkbox']),
textarea {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 10px;
  font: inherit;
}
input[type='checkbox'] {
  width: 20px;
  height: 20px;
  flex: 0 0 20px;
}
.receiving-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  align-items: end;
}
.receiving-products {
  display: grid;
  gap: 6px;
}
.receiving-product {
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid #e2e8f0;
  padding: 9px 0;
  font-size: 0.85rem;
}
.receiving-product > span {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}
.receiving-confirm {
  flex: 1 0 100%;
  display: flex;
  align-items: center;
  padding: 12px 0;
  line-height: 1.5;
}
@media (max-width: 600px) {
  .receiving-lot {
    align-items: flex-start;
    flex-direction: column;
  }
  .receiving-fields {
    grid-template-columns: 1fr 1fr;
  }
  input:not([type='checkbox']),
  textarea {
    font-size: 16px;
  }
}
</style>
