<template>
  <div class="customer-picker">
    <label for="pdv-customer-search">{{ text('customer') }}</label>
    <div v-if="customerName" class="customer-selected">
      <div><strong>{{ customerName }}</strong><small>{{ customerId ? selectedDetails : text('unlinked') }}</small></div>
      <button type="button" class="erp-button erp-button--ghost erp-button--icon" :aria-label="text('remove')"
        :disabled="disabled || selecting" @click="clear">×</button>
    </div>
    <template v-else>
      <input id="pdv-customer-search" ref="input" v-model="query" type="search" autocomplete="off"
        maxlength="120" :placeholder="text('search')" :disabled="disabled || selecting"
        role="combobox" aria-autocomplete="list" aria-controls="pdv-customer-results"
        :aria-expanded="options.length > 0" :aria-activedescendant="active >= 0 ? `pdv-customer-${active}` : undefined"
        @keydown.down.prevent="move(1)" @keydown.up.prevent="move(-1)"
        @keydown.enter.prevent="chooseActive" @keydown.esc="invalidate" />
      <p v-if="selecting || loading" role="status">{{ text(selecting ? 'linking' : 'loading') }}</p>
      <p v-else-if="error" class="customer-error" role="alert">{{ error }}</p>
      <p v-else-if="searched && !options.length">{{ text('empty') }}</p>
      <p v-else-if="!searched">{{ text('hint') }}</p>
      <ul v-if="options.length" id="pdv-customer-results" role="listbox" :aria-label="text('customer')">
        <li v-for="(option, index) in options" :id="`pdv-customer-${index}`" :key="`${option.source}:${option.id}`"
          role="option" :aria-selected="active === index">
          <button type="button" :disabled="disabled || selecting" :class="{ active: active === index }" @click="choose(option)">
            <strong>{{ option.nome }}</strong>
            <span>{{ details(option) }}</span>
            <small>{{ option.source === 'cadastro' ? text('directory') : 'PDV' }}</small>
          </button>
        </li>
      </ul>
      <p v-if="hasMore">{{ text('more') }}</p>
      <button v-if="canUseName" type="button" class="customer-name-only erp-button erp-button--ghost"
        :disabled="disabled || selecting" @click="useName">{{ text('nameOnly') }}</button>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { pdvAPI, type PdvCustomerOption } from '@/services/api'
import { usePdvEntryText } from './entryMessages'

const props = defineProps<{ customerId: string | null; customerName: string | null; disabled?: boolean }>()
const emit = defineEmits<{
  (event: 'update:customerId', value: string | null): void
  (event: 'update:customerName', value: string | null): void
  (event: 'busy', value: boolean): void
}>()
const text = usePdvEntryText(), auth = useAuthStore()
const query = ref(''), selectedDetails = ref(''), error = ref('')
const options = ref<PdvCustomerOption[]>([])
const loading = ref(false), selecting = ref(false), searched = ref(false), hasMore = ref(false), active = ref(-1)
const input = ref<HTMLInputElement>()
let request = 0, selectionRequest = 0, timer: ReturnType<typeof setTimeout> | undefined
const canUseName = computed(() => query.value.trim().length >= 2 && /\p{L}/u.test(query.value) && !/\d/.test(query.value))
function details(option: PdvCustomerOption) { return [option.doc, option.telefone, ...option.ceps.map(cep => `CEP ${cep}`)].filter(Boolean).join(' · ') }
function invalidate() {
  request++; clearTimeout(timer); options.value = []; loading.value = false
  searched.value = false; hasMore.value = false; error.value = ''; active.value = -1
}
watch(query, value => {
  invalidate()
  if (value.trim().length < 2 || props.customerName) return
  const current = request
  loading.value = true
  timer = setTimeout(async () => {
    try {
      const result = await pdvAPI.searchCustomers(value.trim())
      if (request !== current) return
      options.value = result.items; hasMore.value = result.has_more; searched.value = true
    } catch { if (request === current) error.value = text('failed') }
    finally { if (request === current) loading.value = false }
  }, 250)
})
watch(() => props.customerName, () => { if (!props.customerName) { query.value = ''; selectedDetails.value = ''; invalidate() } })
watch([() => auth.user?.id, () => auth.token], () => {
  selectionRequest++
  invalidate(); selecting.value = false; emit('busy', false); query.value = ''; selectedDetails.value = ''
}, { flush: 'sync' })
function clear() {
  if (props.disabled || selecting.value) return
  emit('update:customerId', null); emit('update:customerName', null)
  query.value = ''; selectedDetails.value = ''; invalidate(); nextTick(() => input.value?.focus())
}
function move(step: number) { if (options.value.length) active.value = (active.value + step + options.value.length) % options.value.length }
function chooseActive() { if (active.value >= 0 && options.value[active.value]) void choose(options.value[active.value]) }
async function choose(option: PdvCustomerOption) {
  if (props.disabled || selecting.value) return
  const current = ++request
  const selection = ++selectionRequest
  clearTimeout(timer); loading.value = false; selecting.value = true; emit('busy', true); error.value = ''
  try {
    const customer = await pdvAPI.selectCustomer({ id: option.id, source: option.source })
    if (request !== current) return
    selectedDetails.value = details(option)
    emit('update:customerId', customer.id); emit('update:customerName', customer.nome)
    query.value = ''; options.value = []
  } catch (e: any) {
    if (request === current) error.value = typeof e?.response?.data?.detail === 'string' ? e.response.data.detail : text('selectFailed')
  } finally { if (selection === selectionRequest) { selecting.value = false; emit('busy', false) } }
}
function useName() {
  if (!canUseName.value || props.disabled || selecting.value) return
  const name = query.value.trim(); invalidate()
  emit('update:customerId', null); emit('update:customerName', name); query.value = ''
}
onUnmounted(() => { selectionRequest++; invalidate(); emit('busy', false) })
</script>

<style scoped>
.customer-picker { padding: .75rem 1rem; border-bottom: 1px solid #e5e7eb; min-width: 0; }
.customer-picker label { display: block; font-size: .78rem; font-weight: 600; color: #374151; margin-bottom: .35rem; }
.customer-picker input { width: 100%; min-width: 0; box-sizing: border-box; padding: .65rem .75rem; border: 1px solid #d1d5db; border-radius: .5rem; font-size: .85rem; }
.customer-picker input:focus { outline: 2px solid #93c5fd; outline-offset: 1px; }
.customer-picker p { font-size: .75rem; color: #6b7280; margin: .4rem 0 0; }
.customer-picker .customer-error { color: #b91c1c; }
.customer-picker ul { list-style: none; padding: 0; margin: .5rem 0 0; max-height: 240px; overflow-y: auto; overscroll-behavior: contain; border: 1px solid #e5e7eb; border-radius: .5rem; }
.customer-picker li + li { border-top: 1px solid #e5e7eb; }
.customer-picker li button { display: flex; flex-direction: column; gap: .25rem; width: 100%; text-align: left; background: white; border: 0; padding: .65rem .75rem; cursor: pointer; overflow-wrap: anywhere; }
.customer-picker li button:hover, .customer-picker li button.active { background: #eff6ff; }
.customer-picker li span, .customer-picker small { font-size: .72rem; color: #6b7280; }
.customer-selected { display: flex; align-items: center; justify-content: space-between; gap: .5rem; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: .5rem; padding: .45rem .65rem; }
.customer-selected div { min-width: 0; display: flex; flex-direction: column; overflow-wrap: anywhere; font-size: .85rem; }
.customer-name-only { margin-top: .35rem; font-size: .75rem; white-space: normal; text-align: left; }
</style>
