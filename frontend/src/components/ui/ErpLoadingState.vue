<template>
  <div class="erp-loading" role="status" aria-live="polite" aria-atomic="true">
    <p class="erp-loading__label">
      <span class="erp-loading__indicator" aria-hidden="true"></span>{{ label }}
    </p>
    <div v-if="rows" class="erp-loading__preview" aria-hidden="true">
      <span v-for="row in Math.min(5, Math.max(0, rows))" :key="row" class="erp-loading__line" />
    </div>
  </div>
</template>
<script setup lang="ts">
withDefaults(defineProps<{ label: string; rows?: number }>(), { rows: 3 })
</script>
<style scoped>
.erp-loading {
  padding: 16px;
  min-width: 0;
  width: 100%;
  color: var(--color-text-muted, #556277);
}
.erp-loading__label {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
}
.erp-loading__indicator {
  width: 16px;
  height: 16px;
  flex: none;
  border: 2px solid #dbeafe;
  border-right-color: var(--color-brand-600, #2563eb);
  border-radius: 50%;
  animation: erp-loading-turn 0.8s linear infinite;
}
.erp-loading__preview {
  display: grid;
  gap: 14px;
  max-width: 600px;
  margin: 22px auto 0;
}
.erp-loading__line {
  display: block;
  min-height: 16px;
  background: #e9eef5;
  border-radius: 6px;
  animation: erp-loading-breathe 1.8s ease-in-out infinite;
}
.erp-loading__line:nth-child(2) {
  width: 80%;
}
.erp-loading__line:nth-child(3) {
  width: 62%;
}
@keyframes erp-loading-turn {
  to {
    transform: rotate(360deg);
  }
}
@keyframes erp-loading-breathe {
  50% {
    opacity: 0.45;
  }
}
@media (prefers-reduced-motion: reduce) {
  .erp-loading__indicator,
  .erp-loading__line {
    animation: none;
  }
}
@media (forced-colors: active) {
  .erp-loading__indicator {
    border-color: CanvasText;
    border-right-color: transparent;
  }
  .erp-loading__line {
    background: GrayText;
  }
}
</style>
