<template>
  <div class="color-picker">
    <label v-if="label" class="color-label">{{ label }}</label>
    
    <!-- Cor selecionada atual -->
    <div class="selected-color-display">
      <div 
        class="color-preview"
        :style="{ backgroundColor: selectedColor }"
        @click="togglePicker"
      >
        <div class="color-preview-overlay">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zM7 3V1m0 18v2m8-10a4 4 0 00-4-4H7"/>
          </svg>
        </div>
      </div>
      
      <div class="color-info">
        <input 
          v-model="colorInput" 
          @input="updateColorFromInput"
          type="text" 
          class="color-input"
          placeholder="#FFFFFF"
          maxlength="7"
        >
        <span class="color-name">{{ getColorName(selectedColor) }}</span>
      </div>
    </div>

    <!-- Seletor de cores -->
    <div v-if="showPicker" class="color-picker-dropdown">
      <div class="color-picker-header">
        <span>Escolha uma cor</span>
        <button @click="togglePicker" class="close-picker">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>

      <!-- Cores predefinidas -->
      <div class="preset-colors">
        <div class="preset-section">
          <span class="preset-title">Cores Recomendadas</span>
          <div class="preset-grid">
            <div
              v-for="color in presetColors"
              :key="color.hex"
              class="preset-color"
              :class="{ active: selectedColor === color.hex }"
              :style="{ backgroundColor: color.hex }"
              @click="selectColor(color.hex)"
              :title="color.name"
            >
              <div v-if="selectedColor === color.hex" class="check-mark">
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                </svg>
              </div>
            </div>
          </div>
        </div>

        <div class="preset-section">
          <span class="preset-title">Outras Cores</span>
          <div class="preset-grid">
            <div
              v-for="color in additionalColors"
              :key="color.hex"
              class="preset-color"
              :class="{ active: selectedColor === color.hex }"
              :style="{ backgroundColor: color.hex }"
              @click="selectColor(color.hex)"
              :title="color.name"
            >
              <div v-if="selectedColor === color.hex" class="check-mark">
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                </svg>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Input customizado -->
      <div class="custom-color-section">
        <label>Cor Personalizada</label>
        <div class="custom-color-input">
          <input 
            v-model="customColorInput"
            @input="updateFromCustomInput"
            type="text" 
            placeholder="#FFFFFF"
            maxlength="7"
          >
          <input 
            v-model="selectedColor"
            @input="updateColorFromNative"
            type="color" 
            class="native-color-picker"
          >
        </div>
      </div>
    </div>

    <!-- Overlay para fechar o picker -->
    <div v-if="showPicker" class="picker-overlay" @click="togglePicker"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

interface Props {
  modelValue?: string
  label?: string
}

interface Emits {
  (e: 'update:modelValue', value: string): void
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '#3B82F6',
  label: ''
})

const emit = defineEmits<Emits>()

// Estado reativo
const showPicker = ref(false)
const colorInput = ref(props.modelValue)
const customColorInput = ref(props.modelValue)

// Computed
const selectedColor = computed({
  get: () => props.modelValue,
  set: (value: string) => {
    emit('update:modelValue', value)
  }
})

// Cores predefinidas para vendedores
const presetColors = [
  { hex: '#3B82F6', name: 'Azul' },
  { hex: '#EF4444', name: 'Vermelho' },
  { hex: '#10B981', name: 'Verde' },
  { hex: '#F59E0B', name: 'Laranja' },
  { hex: '#8B5CF6', name: 'Roxo' },
  { hex: '#06B6D4', name: 'Ciano' },
  { hex: '#F97316', name: 'Laranja Escuro' },
  { hex: '#84CC16', name: 'Lima' }
]

const additionalColors = [
  { hex: '#1F2937', name: 'Cinza Escuro' },
  { hex: '#6B7280', name: 'Cinza' },
  { hex: '#DC2626', name: 'Vermelho Escuro' },
  { hex: '#059669', name: 'Verde Escuro' },
  { hex: '#7C3AED', name: 'Roxo Escuro' },
  { hex: '#DB2777', name: 'Rosa' },
  { hex: '#0891B2', name: 'Azul Teal' },
  { hex: '#65A30D', name: 'Verde Limão' },
  { hex: '#DC2626', name: 'Vermelho Intenso' },
  { hex: '#7C2D12', name: 'Marrom' },
  { hex: '#451A03', name: 'Marrom Escuro' },
  { hex: '#000000', name: 'Preto' }
]

// Métodos
const togglePicker = () => {
  showPicker.value = !showPicker.value
}

const selectColor = (color: string) => {
  selectedColor.value = color
  colorInput.value = color
  customColorInput.value = color
  showPicker.value = false
}

const updateColorFromInput = () => {
  if (isValidHexColor(colorInput.value)) {
    selectedColor.value = colorInput.value
    customColorInput.value = colorInput.value
  }
}

const updateFromCustomInput = () => {
  if (isValidHexColor(customColorInput.value)) {
    selectedColor.value = customColorInput.value
    colorInput.value = customColorInput.value
  }
}

const updateColorFromNative = () => {
  colorInput.value = selectedColor.value
  customColorInput.value = selectedColor.value
}

const isValidHexColor = (color: string): boolean => {
  return /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/.test(color)
}

const getColorName = (hex: string): string => {
  const allColors = [...presetColors, ...additionalColors]
  const found = allColors.find(c => c.hex.toLowerCase() === hex.toLowerCase())
  return found ? found.name : 'Personalizada'
}

// Watchers
watch(() => props.modelValue, (newValue) => {
  colorInput.value = newValue
  customColorInput.value = newValue
})
</script>

<style scoped>
.color-picker {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.color-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
}

.selected-color-display {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
}

.selected-color-display:hover {
  border-color: #9ca3af;
}

.color-preview {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 6px;
  border: 2px solid #e5e7eb;
  position: relative;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.color-preview:hover {
  transform: scale(1.05);
  border-color: #9ca3af;
}

.color-preview-overlay {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  opacity: 0;
  transition: opacity 0.2s;
  color: white;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
}

.color-preview:hover .color-preview-overlay {
  opacity: 1;
}

.color-preview-overlay svg {
  width: 1.25rem;
  height: 1.25rem;
}

.color-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.color-input {
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 0.875rem;
  font-family: monospace;
  text-transform: uppercase;
  width: 100%;
}

.color-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.color-name {
  font-size: 0.75rem;
  color: #6b7280;
  font-weight: 500;
}

/* Picker Dropdown */
.color-picker-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  z-index: 50;
  padding: 1rem;
}

.color-picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #e5e7eb;
}

.color-picker-header span {
  font-weight: 500;
  color: #374151;
}

.close-picker {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  border: none;
  background: none;
  color: #6b7280;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s;
}

.close-picker:hover {
  background: #f3f4f6;
  color: #374151;
}

.close-picker svg {
  width: 1rem;
  height: 1rem;
}

.preset-colors {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.preset-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.preset-title {
  font-size: 0.75rem;
  font-weight: 500;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.preset-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 0.5rem;
}

.preset-color {
  width: 2rem;
  height: 2rem;
  border-radius: 6px;
  border: 2px solid #e5e7eb;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preset-color:hover {
  transform: scale(1.1);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.preset-color.active {
  border-color: #000000;
  transform: scale(1.1);
}

.check-mark {
  color: white;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
}

.check-mark svg {
  width: 0.875rem;
  height: 0.875rem;
}

.custom-color-section {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e5e7eb;
}

.custom-color-section label {
  display: block;
  font-size: 0.75rem;
  font-weight: 500;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.5rem;
}

.custom-color-input {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.custom-color-input input[type="text"] {
  flex: 1;
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 0.875rem;
  font-family: monospace;
  text-transform: uppercase;
}

.native-color-picker {
  width: 2.5rem;
  height: 2.5rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  background: none;
}

.picker-overlay {
  position: fixed;
  inset: 0;
  z-index: 40;
}

/* Responsivo */
@media (max-width: 640px) {
  .color-picker-dropdown {
    position: fixed;
    inset: 1rem;
    top: auto;
    bottom: 1rem;
    max-height: 80vh;
    overflow-y: auto;
  }
  
  .preset-grid {
    grid-template-columns: repeat(6, 1fr);
  }
}
</style>