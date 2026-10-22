<template>
  <Teleport to="body">
    <div class="grade-manager-backdrop erp-dialog-backdrop" @click.self="closeIfIdle">
      <section v-erp-dialog class="grade-manager erp-dialog erp-dialog--md" role="dialog" aria-modal="true" :aria-label="tr('Gerenciar grade')">
        <header class="grade-manager-header erp-dialog__header">
          <div>
            <h2>{{ tr('Gerenciar grade') }}</h2>
            <p>{{ item ? item.name : groupName }}</p>
          </div>
          <button type="button" data-dialog-close class="erp-button erp-button--secondary erp-button--icon" :aria-label="tr('Fechar')" :disabled="saving" @click="closeIfIdle">×</button>
        </header>

        <div class="grade-manager-body erp-dialog__body">
          <p class="grade-manager-note">{{ tr('Sugestões não alteram a grade até você confirmar o vínculo.') }}</p>
          <template v-if="item">
            <div v-if="item.group_key" class="grade-manager-current">
              <span>{{ tr('Grade atual: {name}', { name: groupName || item.group_key }) }}</span>
              <button v-if="confirmRemovalId !== item.id" type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="saving" @click="confirmRemovalId = item.id">{{ tr('Remover da grade') }}</button>
              <span v-else class="grade-manager-confirm">
                <span>{{ tr('Remover somente o vínculo desta peça?') }}</span>
                <button type="button" class="erp-button erp-button--danger erp-button--sm" :disabled="saving" @click="removeMember(item.id, item.group_key)">{{ tr('Confirmar') }}</button>
                <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="saving" @click="confirmRemovalId = null">{{ tr('Cancelar') }}</button>
              </span>
            </div>
            <h3>{{ tr('Grades sugeridas') }}</h3>
            <p v-if="suggestionsLoading" class="grade-manager-muted" role="status">{{ tr('Buscando sugestões...') }}</p>
            <p v-else-if="suggestionsError" class="grade-manager-error" role="alert">{{ tr('Não foi possível carregar sugestões. Use a busca abaixo.') }}</p>
            <p v-else-if="!suggestedGroups.length" class="grade-manager-muted">{{ tr('Nenhuma grade semelhante encontrada. Busque uma grade pelo nome.') }}</p>
            <div v-else class="grade-manager-options">
              <button v-for="grade in suggestedGroups" :key="grade.group_key" type="button" class="grade-manager-option erp-control"
                :class="{ selected: selectedGroupKey === grade.group_key }" :aria-pressed="selectedGroupKey === grade.group_key" :disabled="saving"
                @click="selectedGroupKey = grade.group_key">
                <span><strong>{{ gradeLabel(grade) }}</strong><small>{{ countLabel(grade.member_count) }} · {{ tr('Mesmo modelo ou características') }}</small></span>
                <span aria-hidden="true">{{ selectedGroupKey === grade.group_key ? '✓' : '›' }}</span>
              </button>
            </div>
            <label class="grade-manager-search-label" for="grade-directory-search">{{ tr('Buscar outra grade') }}</label>
            <input id="grade-directory-search" v-model="search" class="grade-manager-search" type="search" :placeholder="tr('Nome ou referência da grade')" :disabled="saving" />
            <p v-if="directoryLoading" class="grade-manager-muted" role="status">{{ tr('Buscando grades...') }}</p>
            <p v-else-if="directoryError" class="grade-manager-error" role="alert">{{ tr('Não foi possível buscar grades. Tente novamente.') }}</p>
            <div v-else-if="otherGroups.length" class="grade-manager-options grade-manager-scroll">
              <button v-for="grade in otherGroups" :key="grade.group_key" type="button" class="grade-manager-option erp-control"
                :class="{ selected: selectedGroupKey === grade.group_key }" :aria-pressed="selectedGroupKey === grade.group_key" :disabled="saving"
                @click="selectedGroupKey = grade.group_key">
                <span><strong>{{ gradeLabel(grade) }}</strong><small>{{ countLabel(grade.member_count) }}</small></span>
                <span aria-hidden="true">{{ selectedGroupKey === grade.group_key ? '✓' : '›' }}</span>
              </button>
            </div>
            <p v-else-if="search.trim() && !directoryLoading" class="grade-manager-muted">{{ tr('Nenhuma grade encontrada para esta busca.') }}</p>
            <p v-if="item.group_key && selectedGroupKey && selectedGroupKey !== item.group_key" class="grade-manager-warning">
              {{ tr('Esta ação moverá a peça da grade atual para a grade selecionada. Estoque e histórico permanecem iguais.') }}
            </p>
          </template>

          <template v-else>
            <h3>{{ tr('Peças desta grade') }} <small v-if="!membersLoading && !membersError">{{ currentMembers.length }}/{{ membersTotal }}</small></h3>
            <p v-if="membersLoading" class="grade-manager-muted" role="status">{{ tr('Carregando peças da grade...') }}</p>
            <p v-if="membersError" class="grade-manager-error" role="alert">{{ tr('Não foi possível conferir todos os membros da grade. Tente novamente.') }}</p>
            <button v-if="membersError" type="button" class="erp-button erp-button--secondary erp-button--sm" @click="loadMoreMembers">{{ tr('Tentar novamente') }}</button>
            <div class="grade-manager-members grade-manager-scroll">
              <div v-for="member in currentMembers" :key="member.id" class="grade-manager-member">
                <span><strong>{{ member.name }}</strong><small>{{ [member.size, member.color, member.inventory_code || member.sku_internal].filter(Boolean).join(' · ') }}</small></span>
                <button v-if="confirmRemovalId !== member.id" type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="saving" @click="confirmRemovalId = member.id">{{ tr('Remover') }}</button>
                <span v-else class="grade-manager-confirm">
                  <button type="button" class="erp-button erp-button--danger erp-button--sm" :disabled="saving" @click="removeMember(member.id, groupKey!)">{{ tr('Confirmar') }}</button>
                  <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="saving" @click="confirmRemovalId = null">{{ tr('Cancelar') }}</button>
                </span>
              </div>
            </div>
            <button v-if="!membersError && currentMembers.length < membersTotal" type="button" class="erp-button erp-button--secondary erp-button--sm grade-manager-more" :disabled="membersLoading || saving" @click="loadMoreMembers">{{ tr('Carregar mais peças') }}</button>
            <div class="grade-manager-ungroup">
              <button v-if="!confirmUngroup" type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="saving || membersLoading || membersError" @click="confirmUngroup = true">{{ tr('Desagrupar toda a grade') }}</button>
              <div v-else class="grade-manager-confirm-all">
                <p>{{ tr('Confirme para remover {count} vínculos desta grade. Os produtos e saldos permanecem.', { count: membersTotal }) }}</p>
                <button type="button" class="erp-button erp-button--danger erp-button--sm" :disabled="saving" @click="ungroupAll">{{ tr('Confirmar') }}</button>
                <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="saving" @click="confirmUngroup = false">{{ tr('Cancelar') }}</button>
              </div>
            </div>
            <h3>{{ tr('Adicionar produto avulso') }}</h3>
            <p v-if="suggestionsLoading" class="grade-manager-muted" role="status">{{ tr('Buscando sugestões...') }}</p>
            <p v-else-if="suggestionsError" class="grade-manager-error" role="alert">{{ tr('Não foi possível carregar sugestões. Use a busca abaixo.') }}</p>
            <p v-else-if="!suggestedItems.length" class="grade-manager-muted">{{ tr('Nenhuma peça semelhante encontrada. Busque pelo nome ou código.') }}</p>
            <div v-else class="grade-manager-options">
              <button v-for="candidate in suggestedItems" :key="candidate.id" type="button" class="grade-manager-option erp-control"
                :class="{ selected: selectedItemId === candidate.id }" :aria-pressed="selectedItemId === candidate.id" :disabled="saving"
                @click="selectedItemId = candidate.id">
                <span><strong>{{ candidate.name }}</strong><small>{{ [candidate.size, candidate.color, candidate.inventory_code || candidate.sku_internal].filter(Boolean).join(' · ') }}</small></span>
                <span aria-hidden="true">{{ selectedItemId === candidate.id ? '✓' : '›' }}</span>
              </button>
            </div>
            <label class="grade-manager-search-label" for="grade-item-search">{{ tr('Buscar outro produto avulso') }}</label>
            <input id="grade-item-search" v-model="search" class="grade-manager-search" type="search" :placeholder="tr('Nome, código interno ou tamanho')" :disabled="saving" />
            <p v-if="directoryLoading" class="grade-manager-muted" role="status">{{ tr('Buscando produtos...') }}</p>
            <p v-else-if="directoryError" class="grade-manager-error" role="alert">{{ tr('Não foi possível buscar produtos. Tente novamente.') }}</p>
            <div v-else-if="otherItems.length" class="grade-manager-options grade-manager-scroll">
              <button v-for="candidate in otherItems" :key="candidate.id" type="button" class="grade-manager-option erp-control"
                :class="{ selected: selectedItemId === candidate.id }" :aria-pressed="selectedItemId === candidate.id" :disabled="saving"
                @click="selectedItemId = candidate.id">
                <span><strong>{{ candidate.name }}</strong><small>{{ [candidate.size, candidate.color, candidate.inventory_code || candidate.sku_internal].filter(Boolean).join(' · ') }}</small></span>
                <span aria-hidden="true">{{ selectedItemId === candidate.id ? '✓' : '›' }}</span>
              </button>
            </div>
            <p v-else-if="search.trim().length >= 2 && !directoryLoading" class="grade-manager-muted">{{ tr('Nenhum produto avulso encontrado para esta busca.') }}</p>
          </template>
          <p v-if="saveError" class="grade-manager-error" role="alert">{{ tr(saveError) }}</p>
        </div>

        <footer class="grade-manager-footer erp-dialog__footer">
          <button type="button" class="erp-button erp-button--secondary" :disabled="saving" @click="closeIfIdle">{{ tr('Fechar') }}</button>
          <button type="button" class="erp-button erp-button--primary" :disabled="saving || (item ? !selectedGroupKey || selectedGroupKey === item.group_key : !selectedItemId)" @click="attachSelected">
            {{ saving ? tr('Salvando...') : item?.group_key && selectedGroupKey !== item.group_key ? tr('Confirmar transferência') : tr('Vincular à grade') }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { isAxiosError } from 'axios'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { vErpDialog } from '@/directives/erpDialog'
import { inventoryAPI, type InventoryGradeDirectoryEntry, type InventoryItem } from '@/services/api'
import { useInventoryI18n } from './i18n'

const props = defineProps<{
  item?: InventoryItem | null
  groupKey?: string | null
  groupName?: string
  members?: InventoryItem[]
}>()
const emit = defineEmits<{ close: []; changed: [] }>()
const { tr } = useInventoryI18n()
const search = ref('')
const suggestedGroups = ref<InventoryGradeDirectoryEntry[]>([])
const directoryGroups = ref<InventoryGradeDirectoryEntry[]>([])
const suggestedItems = ref<InventoryItem[]>([])
const directoryItems = ref<InventoryItem[]>([])
const selectedGroupKey = ref('')
const selectedItemId = ref('')
const suggestionsLoading = ref(false)
const suggestionsError = ref(false)
const directoryLoading = ref(false)
const directoryError = ref(false)
const saving = ref(false)
const saveError = ref('')
const confirmRemovalId = ref<string | null>(null)
const confirmUngroup = ref(false)
const currentMembers = ref<InventoryItem[]>(props.members || [])
const membersTotal = ref(props.members?.length || 0)
const membersPage = ref(0)
const membersLoading = ref(false)
const membersError = ref(false)
let memberLoadGeneration = 0
let searchTimer: ReturnType<typeof setTimeout> | null = null
let queryGeneration = 0

const otherGroups = computed(() => directoryGroups.value.filter(group =>
  group.group_key !== props.item?.group_key && !suggestedGroups.value.some(candidate => candidate.group_key === group.group_key),
))
const otherItems = computed(() => directoryItems.value.filter(item =>
  !suggestedItems.value.some(candidate => candidate.id === item.id),
))
function closeIfIdle() { if (!saving.value) emit('close') }
function countLabel(count: number) { return count === 1 ? tr('1 item') : tr('{count} itens', { count }) }
function apiErrorMessage(error: unknown): string | null {
  if (!isAxiosError(error)) return null
  const detail: unknown = error.response?.data?.detail
  return typeof detail === 'string' ? detail : null
}
function gradeLabel(grade: InventoryGradeDirectoryEntry) {
  const all = [...suggestedGroups.value, ...directoryGroups.value]
  const duplicates = all.filter(entry => entry.display_name === grade.display_name && entry.group_key !== grade.group_key)
  return duplicates.length ? `${grade.display_name} · #${grade.group_key.slice(-6)}` : grade.display_name
}

async function loadSuggestions() {
  suggestionsLoading.value = true
  suggestionsError.value = false
  try {
    if (props.item) {
      const response = await inventoryAPI.getItemGradeSuggestions(props.item.id)
      suggestedGroups.value = response.groups.filter(group => group.group_key !== props.item?.group_key)
    } else if (props.groupKey) {
      const response = await inventoryAPI.getGroupItemSuggestions(props.groupKey)
      suggestedItems.value = response.items.filter(item => !item.group_key)
    }
  } catch {
    suggestionsError.value = true
  } finally {
    suggestionsLoading.value = false
  }
}

async function loadDirectory(term: string) {
  const generation = ++queryGeneration
  if (!props.item && term.trim().length < 2) {
    directoryItems.value = []
    directoryLoading.value = false
    directoryError.value = false
    return
  }
  directoryLoading.value = true
  directoryError.value = false
  try {
    if (props.item) {
      const response = await inventoryAPI.getGradeDirectory(term.trim())
      if (generation === queryGeneration) directoryGroups.value = response.groups
    } else {
      const response = await inventoryAPI.getItems({ search: term.trim(), ungrouped_only: true, page: 1, page_size: 12, include_images: false })
      if (generation === queryGeneration) directoryItems.value = response.items.filter(item => !item.group_key)
    }
  } catch {
    if (generation === queryGeneration) directoryError.value = true
  } finally {
    if (generation === queryGeneration) directoryLoading.value = false
  }
}

watch(search, term => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { void loadDirectory(term) }, 250)
})
onMounted(() => {
  void loadSuggestions()
  if (props.item) void loadDirectory('')
  else void loadMembers(1)
})
onUnmounted(() => {
  ++queryGeneration
  ++memberLoadGeneration
  if (searchTimer) clearTimeout(searchTimer)
})

async function loadMembers(page: number) {
  if (!props.groupKey || membersLoading.value) return
  const generation = ++memberLoadGeneration
  membersLoading.value = true
  membersError.value = false
  try {
    const response = await inventoryAPI.getGradeMembers(props.groupKey, page)
    if (generation !== memberLoadGeneration) return
    currentMembers.value = page === 1 ? response.items : [...currentMembers.value, ...response.items]
    membersTotal.value = response.total
    membersPage.value = response.page
  } catch {
    if (generation === memberLoadGeneration) membersError.value = true
  } finally {
    if (generation === memberLoadGeneration) membersLoading.value = false
  }
}
function loadMoreMembers() { void loadMembers(membersPage.value + 1) }

async function attachSelected() {
  const itemId = props.item?.id || selectedItemId.value
  const destination = props.item ? selectedGroupKey.value : props.groupKey
  if (!itemId || !destination || saving.value) return
  saving.value = true
  saveError.value = ''
  try {
    await inventoryAPI.attachItemToGrade(itemId, destination, props.item?.group_key || null)
    emit('changed')
  } catch (error: unknown) {
    saveError.value = apiErrorMessage(error) || tr('Não foi possível vincular o produto. Confira a grade e tente novamente.')
  } finally {
    saving.value = false
  }
}

async function removeMember(itemId: string, expectedGroupKey: string) {
  if (saving.value) return
  saving.value = true
  saveError.value = ''
  try {
    await inventoryAPI.removeFromGroup(itemId, expectedGroupKey)
    emit('changed')
  } catch (error: unknown) {
    saveError.value = apiErrorMessage(error) || tr('Não foi possível remover o vínculo. Confira a grade e tente novamente.')
  } finally {
    saving.value = false
    confirmRemovalId.value = null
  }
}

async function ungroupAll() {
  if (!props.groupKey || saving.value || membersLoading.value || membersError.value) return
  saving.value = true
  saveError.value = ''
  try {
    await inventoryAPI.ungroup(props.groupKey)
    emit('changed')
  } catch (error: unknown) {
    saveError.value = apiErrorMessage(error) || tr('Não foi possível remover o vínculo. Confira a grade e tente novamente.')
  } finally {
    saving.value = false
    confirmUngroup.value = false
  }
}
</script>

<style scoped>
.grade-manager-backdrop { position: fixed; inset: 0; z-index: 2100; display: grid; place-items: center; padding: 1rem; background: rgb(15 23 42 / 55%); }
.grade-manager { width: min(100%, 620px); max-height: min(90dvh, 780px); background: #fff; border-radius: 16px; box-shadow: 0 24px 70px rgb(15 23 42 / 24%); overflow: hidden; display: flex; flex-direction: column; }
.grade-manager-header { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; padding: 1rem 1.25rem; }
.grade-manager-header h2 { font-size: 1.05rem; margin: 0; color: #111827; }
.grade-manager-header p { font-size: .82rem; margin: .2rem 0 0; color: #64748b; overflow-wrap: anywhere; }
.grade-manager-body { padding: .85rem 1.25rem; overflow-y: auto; min-height: 0; }
.grade-manager-body h3 { font-size: .85rem; margin: 1.05rem 0 .45rem; color: #1f2937; }
.grade-manager-body h3 small { font-size: .7rem; font-weight: 500; color: #64748b; }
.grade-manager-note, .grade-manager-muted { font-size: .78rem; color: #64748b; margin: .35rem 0 .65rem; }
.grade-manager-current { display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; padding: .65rem; background: #f1f5f9; border-radius: 9px; font-size: .8rem; }
.grade-manager-confirm { display: inline-flex; align-items: center; gap: .35rem; flex-wrap: wrap; font-size: .78rem; }
.grade-manager-options { display: grid; gap: .4rem; }
.grade-manager-scroll { max-height: 180px; overflow-y: auto; }
.grade-manager-option { display: flex; justify-content: space-between; align-items: center; gap: .5rem; width: 100%; min-height: 48px; text-align: left; padding: .52rem .7rem; background: #fff; border: 1px solid #dbe3ee; border-radius: 10px; cursor: pointer; }
.grade-manager-option.selected { border-color: #2563eb; background: #eff6ff; color: #1d4ed8; }
.grade-manager-option span:first-child, .grade-manager-member > span:first-child { display: grid; gap: .15rem; min-width: 0; }
.grade-manager-option strong, .grade-manager-member strong { font-size: .8rem; font-weight: 650; overflow-wrap: anywhere; }
.grade-manager-option small, .grade-manager-member small { font-size: .72rem; color: #64748b; overflow-wrap: anywhere; }
.grade-manager-search-label { display: block; margin: 1rem 0 .35rem; font-size: .78rem; font-weight: 650; color: #374151; }
.grade-manager-search { width: 100%; padding: .62rem .7rem; font-size: 1rem; border: 1px solid #cbd5e1; border-radius: 9px; background: #fff; }
.grade-manager-members { display: grid; gap: .35rem; }
.grade-manager-member { display: flex; align-items: center; justify-content: space-between; gap: .7rem; padding: .45rem .6rem; border: 1px solid #e2e8f0; border-radius: 8px; }
.grade-manager-more { margin-top: .5rem; }
.grade-manager-ungroup { margin-top: .7rem; }
.grade-manager-confirm-all { padding: .65rem; background: #fff7ed; border-radius: 9px; color: #9a3412; font-size: .78rem; }
.grade-manager-confirm-all p { margin: 0 0 .55rem; }
.grade-manager-confirm-all button + button { margin-left: .4rem; }
.grade-manager-warning { padding: .55rem .65rem; margin: .7rem 0 0; background: #fffbeb; color: #92400e; border-radius: 8px; font-size: .78rem; }
.grade-manager-error { color: #b91c1c; font-size: .8rem; margin: .55rem 0; }
.grade-manager-footer { display: flex; justify-content: flex-end; gap: .5rem; padding: .85rem 1.25rem; }
@media (max-width: 600px) {
  .grade-manager-backdrop { padding: .5rem; align-items: end; }
  .grade-manager { max-height: 94dvh; border-radius: 16px 16px 8px 8px; }
  .grade-manager-header, .grade-manager-body, .grade-manager-footer { padding-left: .9rem; padding-right: .9rem; }
  .grade-manager-footer > button { flex: 1; }
}
</style>
