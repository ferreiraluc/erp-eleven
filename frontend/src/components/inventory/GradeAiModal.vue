<template>
  <Teleport to="body">
    <div class="grade-ai-backdrop erp-dialog-backdrop" @click.self="close">
      <section
        v-erp-dialog
        class="grade-ai-dialog erp-dialog erp-dialog--lg"
        role="dialog"
        aria-modal="true"
        :aria-label="n('title')"
      >
        <header class="erp-dialog__header grade-ai-header">
          <h2>{{ n('title') }}</h2>
          <button
            type="button"
            data-dialog-close
            class="erp-button erp-button--secondary erp-button--icon"
            :aria-label="n('close')"
            :disabled="busy === 'apply'"
            @click="close"
          >
            ×
          </button>
        </header>
        <div class="erp-dialog__body grade-ai-body" :aria-busy="!!busy">
          <p
            v-if="error && !(pending && error === n('pending'))"
            class="grade-ai-error"
            role="alert"
          >
            {{ error }}
          </p>
          <p v-if="pending" class="grade-ai-warning" role="status">
            {{ n(recovered ? 'recovered' : 'pending') }}
          </p>
          <template v-if="preview">
            <h3>{{ n('destinationLabel', { name: preview.target_group_key }) }}</h3>
            <p>{{ n('unaffected') }}</p>
            <ul class="grade-ai-products">
              <li v-for="product in preview.items" :key="product.id">
                <strong>{{ product.name }}</strong
                ><small>{{ metadata(product) }}</small>
              </li>
            </ul>
            <p v-if="preview.existing_members.length">
              {{ n('existing', { count: preview.existing_members.length }) }}
            </p>
            <details v-if="preview.existing_members.length">
              <summary>{{ n('existingGroup') }}</summary>
              <ul class="grade-ai-products">
                <li v-for="product in preview.existing_members" :key="product.id">
                  {{ product.name }}<small>{{ metadata(product) }}</small>
                </li>
              </ul>
            </details>
            <p
              v-for="group in preview.source_groups"
              :key="group.group_key"
              class="grade-ai-warning"
            >
              {{
                n('remaining', {
                  moving: group.moving_count,
                  name: group.group_key,
                  remaining: group.remaining_count,
                })
              }}
            </p>
            <ul v-if="preview.warnings.length" class="grade-ai-warning">
              <li v-for="warning in preview.warnings" :key="warning">{{ warning }}</li>
            </ul>
            <label v-if="!pending" class="grade-ai-check"
              ><input v-model="consent" type="checkbox" :disabled="!!busy" />{{
                n('consent')
              }}</label
            >
          </template>
          <template v-else-if="analysis">
            <p>
              {{
                n('analyzed', { count: analysis.analyzed_count, photos: analysis.photos_analyzed })
              }}
            </p>
            <ul v-if="analysis.warnings.length" class="grade-ai-warning">
              <li v-for="warning in analysis.warnings" :key="warning">{{ warning }}</li>
            </ul>
            <p v-if="!analysis.suggestions.length">{{ n('empty') }}</p>
            <article
              v-for="(suggestion, index) in analysis.suggestions"
              :key="index"
              class="grade-ai-advice"
              :class="{ chosen: chosenIndex === index }"
            >
              <h3>
                {{ n('suggestion', { number: index + 1, count: suggestion.item_ids.length }) }}
              </h3>
              <small>{{ n(suggestion.confidence) }}</small>
              <ul>
                <li v-for="evidence in suggestion.evidence" :key="evidence">{{ evidence }}</li>
              </ul>
              <p v-for="warning in suggestion.warnings" :key="warning" class="grade-ai-warning">
                {{ warning }}
              </p>
              <div class="grade-ai-candidates">
                <label
                  v-for="product in productsFor(suggestion)"
                  :key="product.id"
                  class="grade-ai-product"
                >
                  <input
                    v-if="chosenIndex === index"
                    type="checkbox"
                    :checked="chosenIds.includes(product.id)"
                    :aria-label="n('selectItem', { name: product.name })"
                    :disabled="!!busy"
                    @change="toggleProduct(product.id)"
                  />
                  <ProductThumbnail
                    v-if="product.has_image"
                    :item="thumbnail(product)"
                    alt=""
                    class="grade-ai-thumb"
                  />
                  <span
                    ><strong>{{ product.name }}</strong
                    ><small>{{ metadata(product) }}</small
                    ><small v-if="product.group_key">{{ product.group_key }}</small></span
                  >
                </label>
              </div>
              <button
                v-if="chosenIndex !== index"
                type="button"
                class="erp-button erp-button--secondary erp-button--sm"
                :disabled="!!busy"
                @click="choose(index)"
              >
                {{ n('selected') }}
              </button>
            </article>
            <fieldset v-if="chosenIndex !== null" class="grade-ai-destination" :disabled="!!busy">
              <legend>{{ n('destination') }}</legend>
              <ErpSelect v-model="destinationMode" :label="n('destination')"
                ><option value="new">{{ n('newGroup') }}</option>
                <option value="existing">{{ n('existingGroup') }}</option></ErpSelect
              >
              <label v-if="destinationMode === 'new'"
                >{{ n('name') }}<input v-model="newName" type="text" maxlength="100"
              /></label>
              <ErpDropdown
                v-else
                v-model="targetKey"
                :label="n('choose')"
                :placeholder="n('choose')"
                :options="destinations"
              />
            </fieldset>
          </template>
          <template v-else>
            <p>{{ n('intro') }}</p>
            <p>{{ n('selection', { count: itemIds.length }) }}</p>
            <p v-if="!validSelection" class="grade-ai-warning">{{ n('limit') }}</p>
            <label class="grade-ai-check"
              ><input v-model="includePhotos" type="checkbox" :disabled="!!busy" />{{
                n('photos')
              }}</label
            >
          </template>
          <p v-if="busy" role="status">
            {{
              n(busy === 'analyze' ? 'analyzing' : busy === 'preview' ? 'preparing' : 'applying')
            }}
          </p>
        </div>
        <footer class="erp-dialog__footer grade-ai-footer">
          <button
            v-if="!pending && (analysis || preview || recoveryInvalid)"
            type="button"
            class="erp-button erp-button--secondary"
            :disabled="!!busy"
            @click="back"
          >
            {{ n(recoveryInvalid ? 'reset' : 'back') }}
          </button>
          <button
            v-else
            type="button"
            class="erp-button erp-button--secondary"
            :disabled="busy === 'apply'"
            @click="close"
          >
            {{ n('close') }}
          </button>
          <button
            v-if="preview"
            type="button"
            class="erp-button erp-button--primary"
            :disabled="!!busy || (!pending && !consent)"
            @click="apply"
          >
            {{ n(busy === 'apply' ? 'applying' : pending ? 'retry' : 'apply') }}
          </button>
          <button
            v-else-if="analysis && chosenIndex !== null"
            type="button"
            class="erp-button erp-button--primary"
            :disabled="!canPreview || !!busy"
            @click="prepare"
          >
            {{ n(busy === 'preview' ? 'preparing' : 'review') }}
          </button>
          <button
            v-else-if="!analysis"
            type="button"
            class="erp-button erp-button--primary"
            :disabled="!validSelection || !!busy || recoveryInvalid"
            @click="analyze"
          >
            {{ n(busy === 'analyze' ? 'analyzing' : 'analyze') }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { vErpDialog } from '@/directives/erpDialog'
import { useAuthStore } from '@/stores/auth'
import {
  clearGradePreview,
  gradeError,
  inventoryGradeAi,
  restoreGradePreview,
  saveGradePreview,
  type GradeAdvice,
  type GradeAnalysis,
  type GradePreview,
  type GradeProduct,
} from '@/services/inventoryGradeAi'
import ErpDropdown from '@/components/ui/ErpDropdown.vue'
import ErpSelect from '@/components/ui/ErpSelect.vue'
import ProductThumbnail from './ProductThumbnail.vue'
import { useGradeAiText } from './gradeAiMessages'
const props = defineProps<{ itemIds: string[]; existingGroupKeys?: string[] }>()
const emit = defineEmits<{ close: []; applied: [groupKey: string, count: number] }>()
const auth = useAuthStore(),
  n = useGradeAiText(),
  userId = auth.user?.id || ''
const includePhotos = ref(true),
  analysis = ref<GradeAnalysis | null>(null),
  preview = ref<GradePreview | null>(null)
const chosenIndex = ref<number | null>(null),
  chosenIds = ref<string[]>([]),
  destinationMode = ref('new'),
  newName = ref(''),
  targetKey = ref('')
const consent = ref(false),
  error = ref(''),
  pending = ref(false),
  recovered = ref(false),
  recoveryInvalid = ref(false)
const busy = ref<'analyze' | 'preview' | 'apply' | null>(null)
let alive = true,
  generation = 0,
  controller: AbortController | undefined
const validSelection = computed(
  () =>
    props.itemIds.length >= 2 &&
    props.itemIds.length <= 24 &&
    new Set(props.itemIds).size === props.itemIds.length,
)
const destinations = computed(() =>
  [
    ...new Set([
      ...(props.existingGroupKeys || []),
      ...(analysis.value?.products.map((p) => p.group_key).filter((key): key is string => !!key) ||
        []),
    ]),
  ].map((value) => ({ value, label: value })),
)
const canPreview = computed(
  () =>
    chosenIds.value.length >= 2 &&
    (destinationMode.value === 'new' ? !!newName.value.trim() : !!targetKey.value),
)
const metadata = (p: GradeProduct) =>
  [p.brand, p.category, p.size, p.color].filter(Boolean).join(' · ')
const thumbnail = (p: GradeProduct) => ({
  id: p.id,
  has_image: p.has_image,
  image_data: null,
  updated_at: p.version,
})
const productsFor = (s: GradeAdvice) =>
  analysis.value?.products.filter((p) => s.item_ids.includes(p.id)) || []
function close() {
  if (busy.value !== 'apply') emit('close')
}
function choose(index: number) {
  if (busy.value) return
  chosenIndex.value = index
  chosenIds.value = [...analysis.value!.suggestions[index].item_ids]
  const product = productsFor(analysis.value!.suggestions[index])[0]
  newName.value = (product?.name || '').slice(0, 100)
  targetKey.value = product?.group_key || ''
  destinationMode.value = targetKey.value ? 'existing' : 'new'
  error.value = ''
}
function toggleProduct(id: string) {
  if (busy.value) return
  chosenIds.value = chosenIds.value.includes(id)
    ? chosenIds.value.filter((value) => value !== id)
    : [...chosenIds.value, id]
}
async function analyze() {
  if (!validSelection.value || busy.value || pending.value || recoveryInvalid.value) return
  const mine = ++generation
  controller = new AbortController()
  busy.value = 'analyze'
  error.value = ''
  try {
    const result = await inventoryGradeAi.analyze(
      [...props.itemIds],
      includePhotos.value,
      controller.signal,
    )
    if (alive && mine === generation) {
      analysis.value = result
      chosenIndex.value = null
      chosenIds.value = []
    }
  } catch (e) {
    if (alive && mine === generation) error.value = gradeError(e, n('analyzeError'))
  } finally {
    if (alive && mine === generation) busy.value = null
  }
}
async function prepare() {
  if (!analysis.value || !canPreview.value || busy.value) return
  const mine = ++generation
  controller = new AbortController()
  busy.value = 'preview'
  error.value = ''
  try {
    const result = await inventoryGradeAi.preview(
      {
        item_ids: [...chosenIds.value],
        ...(destinationMode.value === 'new'
          ? { new_group_name: newName.value.trim() }
          : { target_group_key: targetKey.value }),
        expected_versions: Object.fromEntries(
          analysis.value.products
            .filter((p) => chosenIds.value.includes(p.id))
            .map((p) => [p.id, p.version]),
        ),
      },
      controller.signal,
    )
    if (alive && mine === generation) {
      preview.value = result
      consent.value = false
    }
  } catch (e) {
    if (alive && mine === generation) error.value = gradeError(e, n('previewError'))
  } finally {
    if (alive && mine === generation) busy.value = null
  }
}
async function apply() {
  if (!preview.value || busy.value || (!pending.value && !consent.value)) return
  try {
    saveGradePreview(userId, preview.value)
  } catch {
    error.value = n('storageError')
    return
  }
  const mine = ++generation
  busy.value = 'apply'
  error.value = ''
  pending.value = true
  try {
    const result = await inventoryGradeAi.apply(preview.value.preview_token)
    if (alive && mine === generation) {
      try {
        clearGradePreview(userId)
      } catch {
        /* committed result remains successful */
      }
      pending.value = false
      emit('applied', result.target_group_key, result.applied_count)
    }
  } catch (e) {
    if (alive && mine === generation) {
      const status = (e as { response?: { status?: number } })?.response?.status
      if (status && [400, 403, 404, 409, 410, 422].includes(status)) {
        pending.value = false
        recovered.value = false
        try {
          clearGradePreview(userId)
        } catch {
          /* next restore still requires server validation */
        }
        consent.value = false
      }
      error.value = gradeError(e, n(pending.value ? 'pending' : 'saveError'))
    }
  } finally {
    if (alive && mine === generation) busy.value = null
  }
}
function back() {
  if (busy.value || pending.value) return
  error.value = ''
  consent.value = false
  if (recoveryInvalid.value) {
    try {
      clearGradePreview(userId)
    } catch {
      error.value = n('storageError')
      return
    }
    recoveryInvalid.value = false
  } else if (preview.value) preview.value = null
  else {
    analysis.value = null
    chosenIndex.value = null
    chosenIds.value = []
  }
}
onMounted(() => {
  if (!userId) return
  try {
    const saved = restoreGradePreview(userId)
    if (saved) {
      preview.value = saved
      pending.value = true
      recovered.value = true
    }
  } catch {
    error.value = n('recoveryError')
    recoveryInvalid.value = true
  }
})
watch(
  () => auth.user?.id,
  (id) => {
    if (id !== userId) {
      generation++
      controller?.abort()
      emit('close')
    }
  },
)
onBeforeUnmount(() => {
  alive = false
  generation++
  controller?.abort()
})
</script>
<style scoped>
.grade-ai-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2500;
  display: grid;
  place-items: center;
  padding: 16px;
  background: rgb(15 23 42 / 55%);
}
.grade-ai-dialog {
  width: min(100%, 760px);
  max-height: 92dvh;
  background: white;
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.grade-ai-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px;
}
.grade-ai-header h2 {
  font-size: 18px;
  margin: 0;
}
.grade-ai-body {
  overflow: auto;
  padding: 12px 20px;
  min-height: 0;
  color: #334155;
  font-size: 14px;
}
.grade-ai-body h3 {
  font-size: 15px;
  margin: 8px 0;
}
.grade-ai-body p {
  margin: 8px 0;
}
.grade-ai-body ul {
  padding-left: 20px;
}
.grade-ai-error {
  color: #b91c1c;
  background: #fef2f2;
  padding: 10px;
  border-radius: 8px;
}
.grade-ai-warning {
  color: #92400e;
  background: #fffbeb;
  padding: 8px;
  border-radius: 8px;
  overflow-wrap: anywhere;
}
.grade-ai-advice {
  border: 1px solid #dbe3ed;
  border-radius: 12px;
  padding: 12px;
  margin: 12px 0;
}
.grade-ai-advice.chosen {
  border-color: #818cf8;
  background: #fafaff;
}
.grade-ai-advice > small {
  color: #64748b;
}
.grade-ai-product {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px 0;
}
.grade-ai-product > span {
  flex: 1;
  min-width: 0;
}
.grade-ai-product strong,
.grade-ai-product small,
.grade-ai-products small {
  display: block;
  overflow-wrap: anywhere;
}
.grade-ai-product small,
.grade-ai-products small {
  color: #64748b;
  font-size: 12px;
}
.grade-ai-thumb {
  width: 48px;
  height: 48px;
  object-fit: contain;
  flex-shrink: 0;
  border-radius: 6px;
}
.grade-ai-check {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 14px 0;
}
.grade-ai-check input,
.grade-ai-product input {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  accent-color: #4f46e5;
}
.grade-ai-destination {
  display: grid;
  gap: 12px;
  border: 0;
  padding: 8px 0;
}
.grade-ai-destination legend {
  font-weight: 600;
}
.grade-ai-destination > label {
  display: grid;
  gap: 6px;
}
.grade-ai-destination input {
  min-height: 42px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 8px;
  width: 100%;
  box-sizing: border-box;
}
.grade-ai-products {
  list-style: none;
  padding: 0 !important;
}
.grade-ai-products > li {
  border-bottom: 1px solid #e2e8f0;
  padding: 8px 0;
}
.grade-ai-footer {
  padding: 14px 20px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-shrink: 0;
  border-top: 1px solid #e2e8f0;
}
.grade-ai-footer > button {
  max-width: 100%;
  white-space: normal;
}
@media (max-width: 600px) {
  .grade-ai-backdrop {
    padding: 8px;
  }
  .grade-ai-header,
  .grade-ai-footer {
    padding: 12px;
  }
  .grade-ai-body {
    padding: 10px 12px;
  }
  .grade-ai-footer > button {
    flex: 1;
    min-width: 0;
  }
  .grade-ai-dialog {
    max-height: 94dvh;
  }
}
</style>
