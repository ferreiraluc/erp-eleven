<template>
  <img ref="image" :src="src || placeholder" :alt="alt" decoding="async" />
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { inventoryAPI, type InventoryItem } from '@/services/api'

const props = withDefaults(defineProps<{
  item: Pick<InventoryItem, 'id' | 'image_data' | 'has_image' | 'updated_at'>
  alt?: string
}>(), { alt: '' })
const placeholder = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"%3E%3Crect width="64" height="64" fill="%23f1f5f9"/%3E%3Cpath d="M16 44l12-14 8 8 6-6 8 12z" fill="%23cbd5e1"/%3E%3C/svg%3E'
const image = ref<HTMLImageElement | null>(null)
const src = ref<string | null>(null)
let observer: IntersectionObserver | undefined
let generation = 0
watch(() => [image.value, props.item.id, props.item.updated_at, props.item.image_data, props.item.has_image], () => {
  const request = ++generation
  observer?.disconnect()
  src.value = props.item.image_data || null
  if (src.value || !image.value || !props.item.has_image) return
  const id = props.item.id
  let started = false
  const load = async () => {
    if (started) return
    started = true
    observer?.disconnect()
    try {
      const result = await inventoryAPI.getThumbnail(id)
      if (request === generation) src.value = result.image_data
    } catch { /* Keep the placeholder; the product and its actions remain usable. */ }
  }
  if (typeof IntersectionObserver === 'undefined') { void load(); return }
  observer = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) void load()
  }, { rootMargin: '100px' })
  observer.observe(image.value)
}, { flush: 'post' })
onBeforeUnmount(() => { generation++; observer?.disconnect() })
</script>
