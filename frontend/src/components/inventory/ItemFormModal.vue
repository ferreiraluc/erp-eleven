<template>
  <ProductVariantsModal v-if="variantMode && item" :item-id="item.id" :mode="variantMode" @close="variantMode = null" @saved="emit('variants-created', $event)" />
  <ProductHistoryModal v-if="showHistory && item" :item-id="item.id" :initial-section="historySection" @close="closeHistory" />
  <ItemDeleteModal v-if="showDeletion && item && canDeletePermanently" :item-id="item.id" @close="closeDeletion" @history="openHistory" @deleted="emit('deleted', $event)" />
  <div v-show="!showDeletion && !showHistory && !variantMode" class="modal-overlay erp-dialog-backdrop" @click.self="emit('close')">
    <div v-erp-dialog="!showDeletion && !showHistory && !variantMode" class="modal-container erp-dialog" :class="{ 'intake-modal': !isEdit }" role="dialog" aria-modal="true" :aria-label="tr(isEdit ? 'Editar Item' : 'Novo Item')">
      <div class="modal-header erp-dialog__header">
        <h2>{{ isEdit ? tr('Editar Item') : tr('Novo Item') }}</h2>
        <button v-if="isEdit" ref="historyButton" type="button" class="erp-button erp-button--secondary erp-button--sm" @click="openHistory('movements')">{{ tr('Histórico') }}</button>
        <button data-dialog-close @click="emit('close')" :aria-label="tr('Fechar')" class="close-btn erp-button erp-button--secondary erp-button--icon">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="tabs erp-dialog__tabs" :aria-label="tr('Etapas do cadastro')">
        <button v-if="!isEdit" class="erp-control tab" :class="{ active: activeTab === 'capture' }" :aria-current="activeTab === 'capture' ? 'step' : undefined" @click="activeTab = 'capture'">1 · {{ tr('Foto e etiqueta') }}</button>
        <button class="erp-control tab" :class="{ active: activeTab === 'basic' }" :aria-current="activeTab === 'basic' ? 'step' : undefined" @click="activeTab = 'basic'">{{ isEdit ? tr('Básico') : '2 · ' + tr('Conferência') }}</button>
        <button class="erp-control tab" :class="{ active: activeTab === 'stock' }" :aria-current="activeTab === 'stock' ? 'step' : undefined" @click="activeTab = 'stock'">{{ isEdit ? tr('Estoque') : '3 · ' + tr('Estoque') }}</button>
        <button v-if="isEdit" class="erp-control tab" :class="{ active: activeTab === 'photo' }" @click="activeTab = 'photo'">{{ tr('Foto') }}<span v-if="form.image_data" class="tab-dot"></span></button>
      </div>

      <div ref="modalBody" class="modal-body erp-dialog__body">
        <div v-if="isEdit && canCreateVariants" class="stock-readout variant-entry">
          <p>{{ tr('Use os dados já salvos para criar outros tamanhos com a mesma foto.') }}</p>
          <div class="variant-actions">
            <button type="button" class="erp-button erp-button--secondary erp-button--sm" @click="variantMode = 'duplicate'">{{ tr('Duplicar produto') }}</button>
            <button type="button" class="erp-button erp-button--secondary erp-button--sm" @click="variantMode = 'grade'">{{ tr('Adicionar grade') }}</button>
          </div>
        </div>
        <div v-if="isEdit && item" class="stock-readout">
          <div class="stock-readout-values">
            <span>{{ tr('Total salvo') }}: <strong>{{ displayStock(item.current_stock) }}</strong></span>
            <span>{{ tr('Loja:') }} <strong>{{ displayStock(item.stock_loja) }}</strong></span>
            <span>{{ tr('Depósito:') }} <strong>{{ displayStock(item.stock_deposito) }}</strong></span>
          </div>
          <div v-if="!hasKnownStock(item)" role="status" class="stock-readout-warning">
            <strong>{{ tr('Revisar estoque') }}</strong>
            <p>{{ tr('Os dados do produto podem ser editados. Salvar não preenche nem altera os saldos não informados.') }}</p>
          </div>
        </div>
        <div v-if="partialItems.length || uncertainSave" class="partial-save-warning" role="alert">
          <strong>{{ tr(partialItems.length ? 'Cadastro parcialmente concluído' : 'Não foi possível confirmar o cadastro') }}</strong>
          <p>{{ tr(partialItems.length ? 'Itens já criados: {count}. Uma etapa seguinte falhou; o estoque inicial pode estar incompleto.' : 'A conexão foi interrompida. Confira o inventário antes de tentar criar novamente.', { count: partialItems.length }) }}</p>
          <ul v-if="partialItems.length"><li v-for="created in partialItems" :key="created.id">{{ created.name }} · {{ created.sku_internal }}</li></ul>
          <p>{{ tr('Feche esta janela, confira os itens e use Movimentar para concluir apenas o estoque que faltar. O cadastro não será repetido aqui.') }}</p>
        </div>
        <div v-if="activeTab === 'capture'" class="tab-content intake-capture">
          <p class="intake-hint">{{ tr('Use a foto da peça, a etiqueta ou as duas. Você também pode continuar sem imagens e preencher manualmente.') }}</p>
          <div class="intake-sources">
            <section class="intake-source">
              <img v-if="form.image_data" :src="form.image_data" :alt="tr('Foto do produto')" class="intake-thumbnail" />
              <span v-else class="intake-source-icon" aria-hidden="true">📷</span>
              <h3>{{ tr('Foto do produto') }} <small>{{ tr('Opcional') }}</small></h3>
              <p>{{ tr('Nome, categoria, cor e foto de catálogo. Marca e tamanho somente quando legíveis.') }}</p>
              <div class="intake-photo-actions">
                <button type="button" class="erp-button erp-button--secondary erp-button--sm" @click="openProductPhoto()">{{ tr(photoAdded ? 'Rever foto' : 'Adicionar foto') }}</button>
                <button type="button" class="erp-button erp-button--primary erp-button--sm" @click="openProductPhoto(true)">{{ tr('Gerar foto no cabide') }}</button>
              </div>
            </section>
            <section class="intake-source">
              <span class="intake-source-icon" aria-hidden="true">🏷️</span>
              <h3>{{ tr('Etiqueta') }} <small>{{ tr('Opcional') }}</small></h3>
              <p>{{ tr('Texto, marca, tamanho, código de barras e preço com moeda. Complementa os dados da foto.') }}</p>
              <span v-if="labelAdded" class="intake-ready">{{ tr('Leitura adicionada') }}</span>
              <button type="button" class="erp-button erp-button--secondary erp-button--sm" @click="showOcr = true">{{ tr(labelAdded ? 'Rever etiqueta' : 'Ler etiqueta') }}</button>
            </section>
          </div>
          <p v-if="photoAdded || labelAdded" class="intake-hint" role="status">{{ tr('Dados reunidos para conferência. Nenhum produto foi criado.') }}</p>
          <p v-if="conflicts.length" class="intake-conflict-note">{{ tr('Há {count} diferenças para conferir entre as sugestões e o formulário.', { count: conflicts.length }) }}</p>
          <button type="button" class="erp-button erp-button--ghost erp-button--sm" @click="showLabelTemplates = true">{{ ocrText('savedExamples') }}</button>
        </div>
        <!-- ── Basic Tab ── -->
        <div v-if="activeTab === 'basic'" class="tab-content">
          <div class="intake-review-heading">
            <p class="intake-hint">{{ tr('Confira os dados reunidos e complete o que faltar. Código repetido não identifica o mesmo produto.') }}</p>
            <button type="button" class="erp-button erp-button--secondary erp-button--sm" @click="activeTab = 'capture'">{{ tr('Foto e etiqueta') }}</button>
          </div>
          <div v-if="form.image_data" class="intake-images">
            <figure v-if="reviewOriginal && reviewOriginal !== form.image_data"><img :src="reviewOriginal" :alt="tr('Original')" /><figcaption>{{ tr('Original') }}</figcaption></figure>
            <figure><img :src="form.image_data" :alt="tr('Foto do produto')" /><figcaption>{{ tr('Foto do produto') }}</figcaption></figure>
            <button v-if="!isEdit" type="button" class="erp-button erp-button--secondary erp-button--sm" @click="openProductPhoto(true)">{{ tr('Gerar foto no cabide') }}</button>
            <button type="button" class="erp-button erp-button--ghost erp-button--sm" @click="form.image_data = ''; reviewOriginal = ''">{{ tr('Remover foto') }}</button>
          </div>
          <section v-if="conflicts.length" ref="conflictsPanel" class="intake-conflicts" aria-live="polite">
            <h3>{{ tr('Escolha os dados que deseja usar') }}</h3>
            <p>{{ tr('As informações diferentes foram preservadas. Você também pode corrigir o campo e manter o valor do formulário.') }}</p>
            <div v-for="conflict in conflicts" :key="conflict.field + conflict.source" class="intake-conflict">
              <strong>{{ tr(intakeLabels[conflict.field]) }}</strong>
              <button type="button" class="erp-button erp-button--secondary erp-button--sm" @click="resolveConflict(conflict, false)">{{ tr('Manter formulário') }}: {{ currentIntake()[conflict.field] || '—' }}</button>
              <button type="button" class="erp-button erp-button--secondary erp-button--sm" @click="resolveConflict(conflict, true)">{{ tr(conflict.source === 'photo' ? 'Usar foto' : 'Usar etiqueta') }}: {{ conflict.proposed }}</button>
            </div>
          </section>
          <div class="form-group">
            <label>{{ tr('Nome *') }}</label>
            <input ref="nameInput" v-model="form.name" type="text" class="form-input" :class="{ error: errors.name }" :placeholder="tr('Nome do produto')" />
            <span v-if="errors.name" class="error-msg">{{ tr(errors.name) }}</span>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>{{ tr('Marca') }}</label>
              <input v-model="form.brand" type="text" class="form-input" :placeholder="tr('Ex: Armani, Boss...')" list="brand-list" />
              <datalist id="brand-list">
                <option v-for="b in existingBrands" :key="b" :value="b" />
              </datalist>
            </div>
            <div class="form-group">
              <label>{{ tr('Tamanho') }}</label>
              <input v-model="form.size" type="text" class="form-input" placeholder="P, M, G, GG..." />
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>{{ tr('Categoria') }}</label>
              <select v-model="categoryParent" class="form-input">
                <option value="">{{ tr('Selecione...') }}</option>
                <option v-for="cat in parentCategories" :key="cat" :value="cat">{{ tr(cat) }}</option>
                <option value="_custom">{{ tr('Outra...') }}</option>
              </select>
              <input v-if="categoryParent === '_custom'" v-model="categoryCustom" type="text" class="form-input" style="margin-top:0.3rem" :placeholder="tr('Nome da categoria')" />
            </div>
            <div class="form-group">
              <label>{{ tr('Subcategoria') }}</label>
              <input v-model="categorySub" type="text" class="form-input" :placeholder="tr('Ex: Sociais, Tênis...')" :disabled="!categoryParent || categoryParent === '_custom'" list="sub-list" />
              <datalist id="sub-list">
                <option v-for="s in subcategorySuggestions" :key="s" :value="s" />
              </datalist>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>{{ tr('Cor') }}</label>
              <input v-model="form.color" type="text" class="form-input" :placeholder="tr('Vermelho, Azul...')" />
            </div>
            <div class="form-group">
              <label>
                {{ tr('Unidade') }}
                <span v-if="unitAutoSet" class="auto-tag">{{ tr('auto') }}</span>
              </label>
              <select v-model="form.unit" class="form-input">
                <option value="un">{{ tr('un') }}</option>
                <option value="par">{{ tr('par') }}</option>
                <option value="kg">kg</option>
                <option value="m">m</option>
              </select>
            </div>
          </div>
        </div>

        <!-- ── Stock Tab ── -->
        <div v-if="isEdit ? activeTab === 'stock' : activeTab === 'basic'" class="tab-content intake-details">
          <div class="form-group">
            <label>{{ tr('Código de Barras') }}</label>
            <div class="barcode-row">
              <input v-model="form.barcode" type="text" class="form-input" :placeholder="tr('EAN, QR, etc.')" />
              <button @click="showScanner = true" class="scan-btn erp-button erp-button--ghost erp-button--icon" type="button" :title="tr('Escanear')">
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="18" height="18">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8H3a2 2 0 00-2 2v3a2 2 0 002 2h2" />
                </svg>
              </button>
            </div>
            <span v-if="barcodeDuplicateWarning" class="warn-msg">{{ tr('Este código já existe em outro item.') }}</span>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>{{ tr('Custo') }}</label>
              <div class="price-with-currency">
                <select v-model="form.cost_currency" class="currency-select">
                  <option value="PYG">G$</option>
                  <option value="BRL">R$</option>
                  <option value="USD">U$</option>
                  <option value="EUR">€</option>
                </select>
                <input v-model.number="form.cost_price" type="number" step="0.01" min="0" class="form-input price-input" :class="{ error: errors.cost_price }" placeholder="0.00" />
              </div>
              <span v-if="errors.cost_price" class="error-msg">{{ tr(errors.cost_price) }}</span>
            </div>
            <div class="form-group">
              <label>{{ tr('Preço de Venda') }}</label>
              <div class="price-with-currency">
                <select v-model="form.sale_currency" class="currency-select">
                  <option value="PYG">G$</option>
                  <option value="BRL">R$</option>
                  <option value="USD">U$</option>
                  <option value="EUR">€</option>
                </select>
                <input v-model.number="form.sale_price" type="number" step="0.01" min="0" class="form-input price-input" placeholder="0.00" />
              </div>
            </div>
          </div>

          <details class="erp-dialog__section" :open="!!errors.min_stock">
          <summary>{{ tr('Organização e limites (opcional)') }}</summary>
          <div class="form-group">
            <label>{{ tr('Descrição') }}</label>
            <textarea v-model="form.description" class="form-input" rows="2" :placeholder="tr('Descrição opcional')"></textarea>
          </div>
          <div class="form-group">
            <label>{{ tr('Localização') }}</label>
            <input v-model="form.location" type="text" class="form-input" :placeholder="tr('Ex: A-12, Prateleira 3...')" />
          </div>
          <div class="form-group">
            <label>{{ tr('Fornecedor') }}</label>
            <select v-model="form.supplier_id" class="form-input">
              <option value="">{{ tr('Nenhum') }}</option>
              <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>{{ tr('Estoque Mínimo') }}</label>
              <input v-model.number="form.min_stock" type="number" min="0" class="form-input" :class="{ error: errors.min_stock }" />
              <span v-if="errors.min_stock" class="error-msg">{{ tr(errors.min_stock) }}</span>
            </div>
            <div class="form-group">
              <label>{{ tr('Estoque Máximo') }}</label>
              <input v-model.number="form.max_stock" type="number" min="0" class="form-input" />
            </div>
          </div>
          </details>
        </div>
        <div v-if="!isEdit && activeTab === 'stock'" class="tab-content">
          <p v-if="errors.name" class="error-msg" role="alert">{{ tr(errors.name) }}</p>
          <div class="intake-stock-summary">
            <img v-if="form.image_data" :src="form.image_data" :alt="tr('Foto do produto')" />
            <div><strong>{{ form.name || tr('Nome do produto') }}</strong><p>{{ [form.brand, form.size, form.color].filter(Boolean).join(' · ') }}</p><p>{{ tr('O estoque será lançado somente ao concluir o cadastro.') }}</p></div>
          </div>
          <p v-if="!intakeReviewed || conflicts.length" class="intake-conflict-note">{{ tr('Volte à conferência para revisar os dados antes de criar.') }}</p>
          <!-- Initial stock + location — only when creating -->
          <template v-if="!isEdit && activeTab === 'stock'">
            <div class="form-group">
              <label>{{ tr('Cadastrar em') }}</label>
              <div class="loc-toggle">
                <button class="erp-control" type="button" :class="['loc-btn', { active: stockLocation === 'loja' }]" @click="stockLocation = 'loja'">{{ tr('Loja') }}</button>
                <button class="erp-control" type="button" :class="['loc-btn', { active: stockLocation === 'deposito' }]" @click="stockLocation = 'deposito'">{{ tr('Depósito') }}</button>
              </div>
            </div>
            <div v-if="!gradeItemCount" class="form-group">
              <label>{{ tr('Estoque inicial') }}</label>
              <input v-model.number="initialStock" type="number" min="0" class="form-input" placeholder="0" />
              <span class="form-hint">{{ tr('Quantidade adicionada ao {local} ao criar o item.', { local: tr(stockLocation === 'loja' ? 'estoque da loja' : 'depósito') }) }}</span>
            </div>
          </template>
        </div>

        <div v-if="!isEdit && activeTab === 'stock'" class="intake-grade-toggle">
          <button v-if="!gradeEnabled" type="button" class="erp-button erp-button--secondary erp-button--sm" @click="gradeEnabled = true">{{ tr('Criar grade deste modelo') }}</button>
          <button v-else type="button" class="erp-button erp-button--ghost erp-button--sm" @click="disableGrade">{{ tr('Cadastrar apenas esta peça') }}</button>
        </div>
        <!-- Grade creation is explicitly enabled; presets create the selected variants together. -->
        <section v-if="!isEdit && activeTab === 'stock' && gradeEnabled" class="intake-grade">
          <div class="grade-options-heading">
            <h3>{{ tr('Grade de tamanhos e cores (opcional)') }}</h3>
            <button type="button" class="erp-button erp-button--secondary erp-button--sm"
              :aria-pressed="editingGradeOptions" @click="editingGradeOptions = !editingGradeOptions">
              {{ tr(editingGradeOptions ? 'Concluir edição' : 'Editar opções') }}
            </button>
          </div>
          <p v-if="editingGradeOptions" class="form-hint">{{ tr('Remova qualquer botão pelo ×, inclusive os padrões. Produtos cadastrados não são alterados.') }}</p>
          <p v-if="optionRemovalNotice" class="form-hint" role="status">{{ optionRemovalNotice }}</p>
          <div class="tab-content">
          <p class="intake-hint">{{ tr('Escolha um modelo de tamanhos. Cada variação recebe a foto, marca, descrição e preços desta peça. Sem selecionar outras cores, será usada a cor {color}.', { color: form.color || '—' }) }}</p>
          <div class="grade-banner">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16" style="flex-shrink:0">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
            </svg>
            <p>{{ tr('Cria todos os tamanhos de uma vez — cada tamanho vira um item separado agrupado automaticamente.') }}</p>
          </div>

          <!-- Preset buttons -->
          <div class="form-group">
            <label>{{ tr('Modelo de grade') }}</label>
            <div class="grade-presets">
              <span v-for="preset in allPresets" :key="preset.label" class="preset-option">
                <button class="erp-control"
                  @click="applyPreset(preset)"
                  :class="['preset-btn', { active: activePreset === preset.label }]"
                  :aria-pressed="activePreset === preset.label"
                  type="button"
                >
                  {{ preset.custom ? preset.label : tr(preset.label) }}
                </button>
                <button v-if="editingGradeOptions" type="button" class="option-remove erp-control"
                  @click="removePreset(preset.label)"
                  :aria-label="tr('Remover modelo {name}', { name: preset.label })"
                  :title="tr('Remover modelo')">×</button>
              </span>
              <button ref="presetAddButtonRef" class="erp-button erp-button--ghost erp-button--icon"
                @click="showNewPreset ? closePresetInput() : openPresetInput()"
                :class="['preset-btn', 'preset-add-btn', { active: showNewPreset }]"
                type="button"
                :aria-label="tr('Novo modelo de grade')"
                :aria-expanded="showNewPreset"
                :title="tr('Novo modelo de grade')"
              >+</button>
            </div>
            <p v-if="presetStorageError" class="error-msg" role="alert">{{ tr(presetStorageError) }}</p>

            <!-- Inline new-preset form -->
            <div v-if="showNewPreset" class="new-preset-form choice-editor"
              @keydown.esc.stop.prevent="closePresetInput">
              <label>{{ tr('Nome do modelo') }}
                <input ref="presetNameInputRef" v-model="newPresetName" class="form-input" maxlength="60"
                  :placeholder="tr('Ex: M ao 3XL')" @keydown.enter.stop.prevent="saveCustomPreset"
                  @keydown.esc.stop.prevent="closePresetInput" />
              </label>
              <label>{{ tr('Tamanhos do modelo') }}
                <input v-model="newPresetInput" type="text" class="form-input" maxlength="200"
                  placeholder="M, L, XL, 2XL, 3XL" @keydown.enter.stop.prevent="saveCustomPreset"
                  @keydown.esc.stop.prevent="closePresetInput" />
              </label>
              <span class="form-hint">{{ tr('Separe os tamanhos por vírgula ou espaço. Confira a prévia antes de adicionar.') }}</span>
              <div v-if="newPresetSizes.length" class="preset-size-preview" :aria-label="tr('Tamanhos do modelo')">
                <span v-for="size in newPresetSizes" :key="size" class="grade-chip">{{ size }}</span>
              </div>
              <p v-if="presetError" class="error-msg" role="alert">{{ tr(presetError) }}</p>
              <div class="choice-editor-actions">
                <button @click="saveCustomPreset" type="button" class="erp-button erp-button--primary erp-button--sm"
                  :disabled="!newPresetName.trim() || !newPresetSizes.length">{{ tr('Adicionar modelo') }}</button>
                <button @click="closePresetInput" type="button" class="erp-button erp-button--secondary erp-button--sm">{{ tr('Cancelar') }}</button>
              </div>
            </div>
          </div>

          <!-- Size chips -->
          <div class="form-group">
            <label>{{ tr('Tamanhos') }} <span class="size-count">({{ gradeSizes.length }})</span></label>
            <div class="grade-chips" @click="focusChipInput">
              <span v-for="(size, i) in gradeSizes" :key="i" class="grade-chip">
                {{ size }}
                <button @click.stop="removeGradeSize(i)" class="chip-x erp-button erp-button--danger erp-button--icon" type="button">×</button>
              </span>
              <input
                ref="chipInputRef"
                v-model="customSizeInput"
                @keydown.enter.prevent="addCustomSize"
                @keydown="handleComma($event, addCustomSize)"
                @keydown.space.prevent="addCustomSize"
                type="text"
                class="chip-input"
                :placeholder="tr('Ex: 36 ↵')"
              />
            </div>
            <div class="add-size-row">
              <input
                v-model="customSizeInput"
                @keydown.enter.prevent="addCustomSize"
                type="text"
                class="form-input add-size-input"
                :placeholder="tr('Adicionar tamanho (ex: 3XL, 46...)')"
              />
              <button @click="addCustomSize" type="button" class="btn-add-chip erp-button erp-button--primary erp-button--sm">{{ tr('+ Add') }}</button>
            </div>
          </div>

          <!-- Color chips -->
          <div class="form-group">
            <label>{{ tr('Cores') }} <span class="size-count">({{ gradeColors.length }}{{ gradeColors.length > 0 && gradeSizes.length > 0 ? tr(' × {count} tam.', { count: gradeSizes.length }) : '' }})</span></label>
            <div class="quick-colors">
              <span v-for="c in allColors" :key="c" class="color-option">
                <button class="erp-control"
                  @click="toggleQuickColor(c)"
                  :class="['quick-color-btn', { active: gradeColors.some(x => x.toLowerCase() === c.toLowerCase()) }]"
                  :title="gradeColors.some(x => x.toLowerCase() === c.toLowerCase()) ? tr('Já adicionada (remova pelo ×)') : tr('Adicionar')"
                  :aria-pressed="gradeColors.some(x => x.toLowerCase() === c.toLowerCase())"
                  type="button"
                >
                  <span v-if="gradeColors.includes(c)" class="quick-check">✓</span>
                  {{ tr(c) }}
                </button>
                <button v-if="editingGradeOptions" type="button" class="option-remove erp-control"
                  @click="removeColor(c)" :aria-label="tr('Remover cor {name}', { name: c })"
                  :title="tr('Remover cor {name}', { name: c })">×</button>
              </span>
              <div v-if="showColorInput" class="choice-editor quick-color-entry"
                @keydown.esc.stop.prevent="closeColorInput">
                <input
                  ref="colorInputRef"
                  v-model="colorInput"
                  type="text"
                  maxlength="50"
                  :size="Math.min(18, Math.max(8, colorInput.length + 1))"
                  :aria-label="tr('Adicionar cor')"
                  :placeholder="tr('Nova cor')"
                  @keydown.enter.stop.prevent="addGradeColor"
                  @keydown.esc.stop.prevent="closeColorInput"
                />
                <div class="choice-editor-actions">
                  <button type="button" class="erp-button erp-button--primary erp-button--sm"
                    :disabled="!colorInput.trim()" @click="addGradeColor">{{ tr('Adicionar') }}</button>
                  <button type="button" class="erp-button erp-button--ghost erp-button--icon"
                    :aria-label="tr('Cancelar nova cor')" :title="tr('Cancelar')" @click="closeColorInput">×</button>
                </div>
              </div>
              <button v-else ref="colorAddButtonRef" type="button" class="erp-control quick-color-btn quick-color-add"
                :aria-label="tr('Adicionar cor')" :title="tr('Adicionar cor')" @click="openColorInput">+</button>
            </div>
            <p v-if="colorStorageError" class="error-msg" role="alert">{{ tr(colorStorageError) }}</p>
            <span class="form-hint">{{ tr('Modelos e cores adicionados ficam salvos neste navegador para os próximos cadastros.') }}</span>
            <div v-if="gradeColors.length" class="selected-colors">
              <span v-for="(color, i) in gradeColors" :key="i" class="grade-chip grade-chip-color">
                {{ color }}
                <button @click.stop="gradeColors.splice(i, 1)" class="chip-x erp-button erp-button--danger erp-button--icon" type="button">×</button>
              </span>
            </div>
            <span class="form-hint">
              <template v-if="gradeColors.length > 0 && gradeSizes.length > 0">{{ tr('Criará {colors} × {sizes} = {count} itens (cor × tamanho).', { colors: gradeColors.length, sizes: gradeSizes.length, count: gradeItemCount }) }}</template>
              <template v-else-if="gradeColors.length > 0">{{ tr('Itens a criar: {count} (um por cor).', { count: gradeColors.length }) }}</template>
              <template v-else>{{ tr('Cores opcionais — deixe vazio para criar apenas os tamanhos.') }}</template>
            </span>
          </div>

          <!-- Initial stock + location -->
          <div class="form-group">
            <label>{{ tr('Estoque inicial por tamanho') }}</label>
            <input v-model.number="gradeInitialStock" type="number" min="0" class="form-input" placeholder="0" />
            <span class="form-hint">{{ tr('Quantidade adicionada a cada item da grade ao criar.') }}</span>
          </div>
          <div class="form-group" v-if="gradeInitialStock > 0">
            <label>{{ tr('Cadastrar em') }}</label>
            <div class="loc-toggle">
              <button class="erp-control" type="button" :class="['loc-btn', { active: stockLocation === 'loja' }]" @click="stockLocation = 'loja'">{{ tr('Loja') }}</button>
              <button class="erp-control" type="button" :class="['loc-btn', { active: stockLocation === 'deposito' }]" @click="stockLocation = 'deposito'">{{ tr('Depósito') }}</button>
            </div>
          </div>

          <!-- Barcode suffix info -->
          <div v-if="form.barcode" class="grade-barcode-hint">
            <span class="hint-label">{{ tr('Cod. de barras base:') }}</span>
            <code class="hint-code">{{ form.barcode }}</code>
            <span class="hint-arrow">→</span>
            <code class="hint-code">{{ form.barcode }}<strong>{{ gradeSizes[0] || form.size.trim().toUpperCase() }}</strong></code>
            <span>{{ tr('Na grade, o código de barras recebe o tamanho. Cada variação também terá seu próprio SKU.') }}</span>
          </div>

          <!-- Preview -->
          <div v-if="gradeSizes.length > 0 || gradeColors.length > 0" class="form-group">
            <label>{{ tr('Prévia — itens a criar: {count}', { count: gradeItemCount }) }}</label>
            <div class="grade-preview">
              <template v-if="gradeColors.length > 0 && gradeSizes.length > 0">
                <template v-for="color in gradeColors" :key="color">
                  <div v-for="size in gradeSizes" :key="color + size" class="gp-row">
                    <span class="gp-size">{{ size }}</span>
                    <span class="gp-color-badge">{{ color }}</span>
                    <span class="gp-name">{{ (form.name || tr('(nome)')) + ' ' + size + ' ' + color }}</span>
                    <span v-if="form.barcode" class="gp-barcode">{{ form.barcode + size }}</span>
                  </div>
                </template>
              </template>
              <template v-else-if="gradeColors.length > 0">
                <div v-for="color in gradeColors" :key="color" class="gp-row">
                  <span class="gp-color-badge">{{ color }}</span>
                  <span class="gp-name">{{ (form.name || tr('(nome)')) + ' ' + color }}</span>
                  <span v-if="form.size" class="gp-size">{{ form.size.trim().toUpperCase() }}</span>
                  <span v-if="form.barcode" class="gp-barcode">{{ form.barcode + form.size.trim().toUpperCase() }}</span>
                </div>
              </template>
              <template v-else>
                <div v-for="size in gradeSizes" :key="size" class="gp-row">
                  <span class="gp-size">{{ size }}</span>
                  <span class="gp-name">{{ (form.name || tr('(nome)')) + ' ' + size }}</span>
                  <span v-if="form.barcode" class="gp-barcode">{{ form.barcode + size }}</span>
                </div>
              </template>
            </div>
          </div>

          <div v-else class="grade-empty">
            {{ tr('Selecione um modelo acima ou adicione tamanhos e/ou cores.') }}
          </div>
        </div>

        </section>

        <!-- ── Photo Tab ── -->
        <div v-if="activeTab === 'photo'" class="tab-content">
          <!-- Current image preview -->
          <div v-if="form.image_data" class="photo-preview">
            <img :src="form.image_data" :alt="tr('Foto do item')" class="item-photo" />
            <button @click="form.image_data = ''" class="remove-photo erp-button erp-button--danger">{{ tr('× Remover foto') }}</button>
          </div>

          <div v-else class="photo-placeholder">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="40" height="40" class="photo-icon">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <p>{{ tr('Nenhuma foto adicionada') }}</p>
          </div>

          <div class="photo-actions">
            <button @click="photoInputRef?.click()" class="btn btn-secondary erp-button erp-button--secondary" type="button">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
              {{ tr('Galeria') }}
            </button>
            <button @click="showCameraPhoto = true" class="btn btn-secondary erp-button erp-button--secondary" type="button">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                <circle cx="12" cy="13" r="3" stroke="currentColor" stroke-width="2" fill="none" />
              </svg>
              {{ tr('Câmera') }}
            </button>
          </div>

          <input
            ref="photoInputRef"
            type="file"
            accept="image/*"
            class="hidden-input"
            @change="onPhotoFile"
          />

          <!-- Inline camera capture for photo -->
          <div v-if="showCameraPhoto" class="inline-camera">
            <video ref="photoVideoRef" autoplay playsinline class="inline-video"></video>
            <div class="inline-camera-btns">
              <button @click="capturePhoto" class="btn btn-primary erp-button erp-button--primary" type="button">{{ tr('Capturar') }}</button>
              <button @click="stopCameraPhoto" class="btn btn-secondary erp-button erp-button--secondary" type="button">{{ tr('Cancelar') }}</button>
            </div>
          </div>

          <p class="photo-hint">{{ tr('A imagem é redimensionada para 400×400px e armazenada no banco de dados.') }}</p>
        </div>
        <template v-if="activeTab === 'basic' && needsIntakeReview">
          <label class="intake-review-check"><input ref="reviewInput" v-model="intakeReviewed" type="checkbox" :disabled="conflicts.length > 0" />{{ tr('Conferi os dados e a foto escolhida para este produto.') }}</label>
          <p v-if="reviewError" class="error-msg" role="alert">{{ tr(reviewError) }}</p>
        </template>
      </div>

      <div v-if="!isEdit && activeTab === 'stock' && !partialItems.length && !uncertainSave" class="intake-total" role="status">{{ tr('Ao concluir: {items} produto(s), {quantity} unidade(s) no {local}.', { items: gradeItemCount || 1, quantity: gradeItemCount ? gradeItemCount * (gradeInitialStock || 0) : (initialStock || 0), local: tr(stockLocation === 'loja' ? 'estoque da loja' : 'depósito') }) }}</div>
      <div class="modal-footer erp-dialog__footer">
        <button v-if="isEdit && canDeletePermanently" ref="deleteButton" class="delete-product erp-button erp-button--danger" :disabled="saving" @click="showDeletion = true">{{ tr('Excluir definitivamente') }}</button>
        <button @click="emit('close')" class="btn btn-secondary erp-button erp-button--secondary">{{ tr(partialItems.length || uncertainSave ? 'Fechar' : 'Cancelar') }}</button>
        <button v-if="activeTab === 'capture' && !partialItems.length && !uncertainSave" type="button" class="erp-button erp-button--primary" @click="activeTab = 'basic'">{{ tr('Conferir dados') }}</button>
        <button v-else-if="!isEdit && activeTab !== 'stock' && !partialItems.length && !uncertainSave" type="button" class="erp-button erp-button--primary" @click="continueToStock">{{ tr('Continuar para estoque') }}</button>
        <button v-else-if="!partialItems.length && !uncertainSave" @click="handleSubmit" class="btn btn-primary erp-button erp-button--primary" :disabled="saving || (!isEdit && (!intakeReviewed || conflicts.length > 0))">
          <template v-if="saving">{{ tr('Salvando...') }}</template>
          <template v-else-if="isEdit">{{ tr('Atualizar') }}</template>
          <template v-else-if="gradeItemCount > 0">{{ tr('Criar grade ({count} itens)', { count: gradeItemCount }) }}</template>
          <template v-else>{{ tr('Criar') }}</template>
        </button>
      </div>
    </div>

    <ProductPhotoAssistant v-if="photoOpened" :open="showProductPhoto" :start-with-hanger="startWithHanger" draft @result="onProductPhotoResult" @close="showProductPhoto = false" />
    <BarcodeScanner v-if="showScanner" @barcode-detected="onBarcodeDetected" @close="showScanner = false" />
    <OcrScanner v-if="labelOpened" :open="showOcr" draft @result="onOcrResult" @close="showOcr = false" />
    <LabelTemplatesModal v-if="showLabelTemplates" @close="showLabelTemplates = false" />
  </div>
</template>

<script setup lang="ts">
import { vErpDialog } from '@/directives/erpDialog'
import ProductVariantsModal from './ProductVariantsModal.vue'
import type { VariantResult } from '@/services/inventoryVariants'
import { useInventoryI18n } from '@/components/inventory/i18n'
const { tr } = useInventoryI18n()
import { ref, reactive, watch, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { inventoryAPI, type InventoryItem } from '@/services/api'
import { displayStock, hasKnownStock } from '@/services/inventoryStock'
import { GRADE_PRESETS, QUICK_COLORS, PRESETS_KEY, COLORS_KEY, STORAGE_ERROR, optionKey, parseGradeSizes,
  HIDDEN_PRESETS_KEY, HIDDEN_COLORS_KEY, readHiddenOptions, readCustomPresets, readCustomColors,
  readPreference, savePreference, type GradePreset } from '@/services/inventoryGradeOptions'
import BarcodeScanner from './BarcodeScanner.vue'
import ProductPhotoAssistant from './ProductPhotoAssistant.vue'
import ProductHistoryModal from './ProductHistoryModal.vue'
import type { HistorySection } from '@/services/inventoryHistory'
import type { ProductPhotoResult } from '@/services/productPhoto'
import { mergeIntake, type IntakeDraft, type IntakeField, type IntakeConflict, type IntakeSource } from '@/services/productIntake'
import OcrScanner from './OcrScanner.vue'
import type { OcrAppliedFields } from '@/services/ocr'
import { useI18n } from 'vue-i18n'
import { ocrMessages } from './ocrMessages'
const { t: ocrText } = useI18n({ useScope: 'local', messages: ocrMessages })
import LabelTemplatesModal from './LabelTemplatesModal.vue'
import ItemDeleteModal from './ItemDeleteModal.vue'

// ── Text normalization ────────────────────────────────────────────────────────
function toTitleCase(s: string | undefined | null): string {
  if (!s) return ''
  return s.trim().toLowerCase().split(/\s+/).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

const props = defineProps<{
  item?: InventoryItem | null
  suppliers?: Array<{ id: string; name: string }>
  existingGroupKeys?: string[]
  existingBrands?: string[]
  canDeletePermanently?: boolean
  canCreateVariants?: boolean
}>()

const emit = defineEmits<{
  (e: 'saved', item: InventoryItem): void
  (e: 'partial', items: InventoryItem[]): void
  (e: 'close'): void
  (e: 'deleted', id: string): void
  (e: 'variants-created', result: VariantResult): void
}>()

const variantMode = ref<'duplicate' | 'grade' | null>(null)
const showDeletion = ref(false), deleteButton = ref<HTMLButtonElement>()
const showHistory = ref(false), historySection = ref<HistorySection>('movements')
const historyButton = ref<HTMLButtonElement>()
function openHistory(section: HistorySection) { showDeletion.value = false; historySection.value = section; showHistory.value = true }
async function closeHistory() { showHistory.value = false; await nextTick(); historyButton.value?.focus() }
async function closeDeletion() { showDeletion.value = false; await nextTick(); deleteButton.value?.focus() }

const isEdit = computed(() => !!props.item)
const activeTab = ref(props.item ? 'basic' : 'capture')
const modalBody = ref<HTMLElement>(), conflictsPanel = ref<HTMLElement>()
const reviewInput = ref<HTMLInputElement>(), nameInput = ref<HTMLInputElement>()
watch(activeTab, async () => { await nextTick(); if (modalBody.value) modalBody.value.scrollTop = 0 })
const showScanner = ref(false)
const showOcr = ref(false)
const showProductPhoto = ref(false)
const startWithHanger = ref(false)
function openProductPhoto(hanger = false) { startWithHanger.value = hanger; showProductPhoto.value = true }
const showLabelTemplates = ref(false)
const photoOpened = ref(false), labelOpened = ref(false)
watch(showProductPhoto, value => { if (value) photoOpened.value = true })
watch(showOcr, value => { if (value) labelOpened.value = true })
const photoAdded = ref(false), labelAdded = ref(false), intakeReviewed = ref(false)
const reviewOriginal = ref(''), reviewError = ref('')
const needsIntakeReview = computed(() => !isEdit.value || photoAdded.value || labelAdded.value)
const conflicts = ref<IntakeConflict[]>([])
const previousSuggestions: Record<IntakeSource, IntakeDraft> = { photo: {}, label: {} }
const intakeLabels: Record<IntakeField, string> = { name: 'Nome', description: 'Descrição', category: 'Categoria', brand: 'Marca', size: 'Tamanho', color: 'Cor', barcode: 'Código de barras', price: 'Preço de Venda' }
const showCameraPhoto = ref(false)
const saving = ref(false)
const partialItems = ref<InventoryItem[]>([])
const uncertainSave = ref(false)
const barcodeDuplicateWarning = ref(false)
const unitAutoSet = ref(false)
const photoInputRef = ref<HTMLInputElement>()
const photoVideoRef = ref<HTMLVideoElement>()
const chipInputRef = ref<HTMLInputElement>()
let photoStream: MediaStream | null = null

// ── Grade state ──────────────────────────────────────────────────────────────
const gradeSizes = ref<string[]>([])
const gradeEnabled = ref(false)
const editingGradeOptions = ref(false)
const removedOption = ref<{ kind: 'color' | 'preset'; name: string } | null>(null)
const optionRemovalNotice = computed(() => removedOption.value
  ? tr(removedOption.value.kind === 'color' ? 'Cor {name} removida dos botões salvos.' : 'Modelo {name} removido dos botões salvos.', { name: removedOption.value.name })
  : '')
function disableGrade() {
  gradeEnabled.value = false; gradeSizes.value = []; gradeColors.value = []; activePreset.value = ''; gradeInitialStock.value = 0
  colorInput.value = ''; showColorInput.value = false
  editingGradeOptions.value = false; removedOption.value = null
}
const activePreset = ref('')
const customSizeInput = ref('')
const gradeInitialStock = ref(0)
const initialStock = ref(0)

// ── Color grade state ─────────────────────────────────────────────────────────
const customColors = ref(readCustomColors())
const hiddenColors = ref(readHiddenOptions(HIDDEN_COLORS_KEY, QUICK_COLORS))
const allColors = computed(() => [...QUICK_COLORS.filter(c => !hiddenColors.value.includes(optionKey(c))), ...customColors.value])
const colorStorageError = ref('')
const gradeColors = ref<string[]>([])
const colorInput = ref('')
const colorInputRef = ref<HTMLInputElement>()
const colorAddButtonRef = ref<HTMLButtonElement>()
const showColorInput = ref(false)

function openColorInput() { colorStorageError.value = ''; showColorInput.value = true; nextTick(() => colorInputRef.value?.focus()) }
function closeColorInput() {
  colorInput.value = ''; showColorInput.value = false; colorStorageError.value = ''
  nextTick(() => colorAddButtonRef.value?.focus())
}
function addGradeColor() {
  const c = toTitleCase(colorInput.value)
  if (!c) return
  const existing = [...QUICK_COLORS, ...customColors.value].find(x => optionKey(x) === optionKey(c))
  if (existing && hiddenColors.value.includes(optionKey(existing))) {
    const hidden = hiddenColors.value.filter(key => key !== optionKey(existing))
    if (!savePreference(HIDDEN_COLORS_KEY, JSON.stringify(hidden))) { colorStorageError.value = STORAGE_ERROR; return }
    hiddenColors.value = hidden
  } else if (!existing) {
    const colors = [...customColors.value, c]
    if (!savePreference(COLORS_KEY, JSON.stringify(colors))) { colorStorageError.value = STORAGE_ERROR; return }
    customColors.value = colors
  }
  toggleQuickColor(existing || c)
  removedOption.value = null
  closeColorInput()
}
function removeColor(color: string) {
  if (!allColors.value.includes(color)) return
  if (QUICK_COLORS.includes(color)) {
    const hidden = [...hiddenColors.value, optionKey(color)]
    if (!savePreference(HIDDEN_COLORS_KEY, JSON.stringify(hidden))) { colorStorageError.value = STORAGE_ERROR; return }
    hiddenColors.value = hidden
  } else {
    const colors = customColors.value.filter(c => c !== color)
    if (!savePreference(COLORS_KEY, JSON.stringify(colors))) { colorStorageError.value = STORAGE_ERROR; return }
    customColors.value = colors
  }
  colorStorageError.value = ''
  gradeColors.value = gradeColors.value.filter(c => optionKey(c) !== optionKey(color))
  removedOption.value = { kind: 'color', name: color }
  nextTick(() => (colorAddButtonRef.value || colorInputRef.value)?.focus())
}
function toggleQuickColor(c: string) {
  if (!gradeColors.value.some(x => x.toLowerCase() === c.toLowerCase())) {
    gradeColors.value.push(c)
  }
  // To remove, use × on the chip
}
const gradeItemCount = computed(() => {
  const s = gradeSizes.value.length
  const c = gradeColors.value.length
  if (s > 0 && c > 0) return s * c
  if (s > 0) return s
  return c
})
const stockLocation = ref<'loja' | 'deposito'>(
  readPreference('inv_stock_location') === 'deposito' ? 'deposito' : 'loja'
)

watch(stockLocation, (val) => {
  savePreference('inv_stock_location', val)
})

const customPresets = ref<GradePreset[]>(readCustomPresets())
const hiddenPresets = ref(readHiddenOptions(HIDDEN_PRESETS_KEY, GRADE_PRESETS.map(p => p.label)))
const allPresets = computed<GradePreset[]>(() => [...GRADE_PRESETS.filter(p => !hiddenPresets.value.includes(optionKey(p.label))), ...customPresets.value])
const presetStorageError = ref('')

// New-preset inline form state
const presetNameInputRef = ref<HTMLInputElement>()
const presetAddButtonRef = ref<HTMLButtonElement>()
const showNewPreset = ref(false)
const newPresetName = ref('')
const newPresetInput = ref('')
const newPresetSizes = computed(() => parseGradeSizes(newPresetInput.value))
const presetError = ref('')
watch([newPresetName, newPresetInput], () => { presetError.value = ''; presetStorageError.value = '' })

function openPresetInput() {
  presetStorageError.value = ''; showNewPreset.value = true
  nextTick(() => presetNameInputRef.value?.focus())
}
function closePresetInput() {
  showNewPreset.value = false; newPresetName.value = ''; newPresetInput.value = ''; presetError.value = ''
  nextTick(() => presetAddButtonRef.value?.focus())
}

function applyPreset(preset: GradePreset) {
  // The photographed variant must not disappear when applying a preset.
  gradeSizes.value = [...new Set([form.size.trim().toUpperCase(), ...preset.sizes.map(size => size.trim().toUpperCase())].filter(Boolean))]
  activePreset.value = preset.label
}

function saveCustomPreset() {
  const name = newPresetName.value.trim().replace(/\s+/g, ' ')
  if (!name || newPresetSizes.value.length === 0) return
  if (allPresets.value.some(p => optionKey(p.label) === optionKey(name))) {
    presetError.value = 'Já existe um modelo com esse nome. Selecione o botão existente ou use outro nome.'
    return
  }
  const p: GradePreset = { label: name, sizes: [...newPresetSizes.value], custom: true }
  const presets = [...customPresets.value, p]
  if (!savePreference(PRESETS_KEY, JSON.stringify(presets))) { presetStorageError.value = STORAGE_ERROR; return }
  customPresets.value = presets
  removedOption.value = null
  applyPreset(p)
  closePresetInput()
}

function removePreset(label: string) {
  const preset = allPresets.value.find(p => p.label === label)
  if (!preset) return
  if (preset.custom) {
    const presets = customPresets.value.filter(p => p.label !== label)
    if (!savePreference(PRESETS_KEY, JSON.stringify(presets))) { presetStorageError.value = STORAGE_ERROR; return }
    customPresets.value = presets
  } else {
    const hidden = [...hiddenPresets.value, optionKey(label)]
    if (!savePreference(HIDDEN_PRESETS_KEY, JSON.stringify(hidden))) { presetStorageError.value = STORAGE_ERROR; return }
    hiddenPresets.value = hidden
  }
  presetStorageError.value = ''
  if (activePreset.value === label) activePreset.value = ''
  removedOption.value = { kind: 'preset', name: label }
  nextTick(() => presetAddButtonRef.value?.focus())
}

function removeGradeSize(index: number) {
  gradeSizes.value.splice(index, 1)
  activePreset.value = ''
}

function addCustomSize() {
  const s = customSizeInput.value.trim().toUpperCase()
  if (s && !gradeSizes.value.includes(s)) {
    gradeSizes.value.push(s)
    activePreset.value = ''
  }
  customSizeInput.value = ''
}

function focusChipInput() {
  chipInputRef.value?.focus()
}

// Hierarchical category
const parentCategories = ['Camisetas', 'Calças', 'Vestidos', 'Acessórios', 'Calçados', 'Outros']
const categoryParent = ref('')
const categorySub = ref('')
const categoryCustom = ref('')

const subcategorySuggestions = computed(() => {
  const map: Record<string, string[]> = {
    'Calçados': ['Sociais', 'Tênis', 'Mocassim', 'Sandálias', 'Botas', 'Chinelos', 'Sapatilhas'],
    'Camisetas': ['Gola Redonda', 'Polo', 'Regata', 'Manga Longa', 'Cropped'],
    'Calças': ['Jeans', 'Social', 'Moletom', 'Bermuda', 'Short', 'Legging'],
    'Vestidos': ['Casual', 'Festa', 'Midi', 'Longo', 'Curto'],
    'Acessórios': ['Cintos', 'Bolsas', 'Carteiras', 'Chapéus', 'Meias', 'Gravatas'],
  }
  return map[categoryParent.value] || []
})

watch([categoryParent, categorySub, categoryCustom], () => {
  if (categoryParent.value === '_custom') {
    form.category = categoryCustom.value
  } else if (categoryParent.value && categorySub.value) {
    form.category = `${categoryParent.value}>${categorySub.value}`
  } else {
    form.category = categoryParent.value === '_custom' ? '' : categoryParent.value
  }
})

// Category → Unit mapping
const categoryUnitMap: Record<string, string> = {
  'Calçados': 'par',
  'Calcados': 'par',
}

const form = reactive({
  name: '',
  description: '',
  category: '',
  size: '',
  color: '',
  brand: '',
  unit: 'un',
  location: '',
  barcode: '',
  supplier_id: '',
  cost_price: 0,
  sale_price: 0,
  currency: 'PYG',
  cost_currency: 'BRL',
  sale_currency: 'USD',
  min_stock: 0,
  max_stock: 0,
  is_active: true,
  image_data: '',
  group_key: '',
})

const errors = reactive<Record<string, string>>({})

onMounted(() => {
  if (props.item) {
    Object.assign(form, {
      name: props.item.name || '',
      description: props.item.description || '',
      category: props.item.category || '',
      size: props.item.size || '',
      color: props.item.color || '',
      brand: props.item.brand || '',
      unit: props.item.unit || 'un',
      location: props.item.location || '',
      barcode: props.item.barcode || '',
      supplier_id: props.item.supplier_id || '',
      cost_price: Number(props.item.cost_price) || 0,
      sale_price: Number(props.item.sale_price) || 0,
      currency: props.item.currency || 'PYG',
      cost_currency: props.item.cost_currency || 'BRL',
      sale_currency: props.item.sale_currency || 'USD',
      min_stock: props.item.min_stock || 0,
      max_stock: props.item.max_stock || 0,
      image_data: props.item.image_data || '',
      group_key: props.item.group_key || '',
    })
    // Init hierarchical category
    const cat = props.item.category || ''
    const parts = cat.split('>')
    if (parentCategories.includes(parts[0])) {
      categoryParent.value = parts[0]
      categorySub.value = parts[1] || ''
    } else if (cat) {
      categoryParent.value = '_custom'
      categoryCustom.value = cat
    }
  }
})

onUnmounted(() => {
  if (barcodeTimer) clearTimeout(barcodeTimer)
  if (photoStream) photoStream.getTracks().forEach(t => t.stop())
})

// Auto category → unit
watch(() => form.category, (cat) => {
  if (!cat) return
  const mapped = categoryUnitMap[cat]
  if (mapped && mapped !== form.unit) {
    form.unit = mapped
    unitAutoSet.value = true
    setTimeout(() => { unitAutoSet.value = false }, 2000)
  }
})

// Barcode duplicate check
let barcodeTimer: ReturnType<typeof setTimeout> | null = null
watch(() => form.barcode, (val) => {
  if (barcodeTimer) clearTimeout(barcodeTimer)
  barcodeDuplicateWarning.value = false
  if (!val) return
  barcodeTimer = setTimeout(async () => {
    try {
      const items = await inventoryAPI.getByBarcode(val)
      barcodeDuplicateWarning.value = items.filter((i: InventoryItem) => i.id !== props.item?.id).length > 0
    } catch {}
  }, 500)
})

function validate() {
  Object.keys(errors).forEach(k => delete errors[k])
  if (form.name.trim().length < 2) errors.name = 'Nome deve ter ao menos 2 caracteres'
  const startingStock = (gradeSizes.value.length || gradeColors.value.length ? gradeInitialStock.value : initialStock.value) || 0
  if (!isEdit.value && (!Number.isInteger(startingStock) || startingStock < 0 || startingStock > 2_147_483_647)) {
    errors.name = 'Estoque inicial deve ser inteiro, não negativo e dentro do limite permitido.'
  }
  if (form.cost_price < 0) errors.cost_price = 'Custo não pode ser negativo'
  if (form.min_stock > form.max_stock && form.max_stock > 0) errors.min_stock = 'Mínimo não pode ser maior que máximo'
  return Object.keys(errors).length === 0
}

async function handleSubmit() {
  if (saving.value || partialItems.value.length || uncertainSave.value) return
  if (conflicts.value.length || (needsIntakeReview.value && !intakeReviewed.value)) {
    reviewError.value = 'Confira os dados e resolva as diferenças antes de continuar.'
    activeTab.value = 'basic'
    return
  }
  if (!validate()) {
    activeTab.value = errors.name?.startsWith('Estoque inicial') ? 'stock' : 'basic'
    return
  }
  saving.value = true
  const createdItems: InventoryItem[] = []
  let creating = false
  try {
    // ── Grade / color creation ────────────────────────────────────────────────
    if (!isEdit.value && (gradeSizes.value.length > 0 || gradeColors.value.length > 0)) {
      const sharedGroupKey = form.group_key || `grade-${crypto.randomUUID()}`
      const baseGradePayload = {
        name: form.name,
        description: form.description || null,
        category: form.category || null,
        brand: form.brand || null,
        unit: form.unit || 'un',
        location: form.location || null,
        base_barcode: form.barcode || null,
        supplier_id: form.supplier_id || null,
        cost_price: form.cost_price,
        sale_price: form.sale_price,
        currency: form.currency,
        cost_currency: form.cost_currency,
        sale_currency: form.sale_currency,
        min_stock: form.min_stock,
        max_stock: form.max_stock,
        image_data: form.image_data || null,
        group_key: sharedGroupKey,
        sizes: gradeSizes.value,
        initial_stock: gradeInitialStock.value || 0,
        stock_location: stockLocation.value,
      }

      let firstItem: InventoryItem | null = null

      if (gradeSizes.value.length > 0 && gradeColors.value.length > 0) {
        // Size × color matrix
        for (const color of gradeColors.value) {
          creating = true
          const result = await inventoryAPI.createGrade({ ...baseGradePayload, color })
          creating = false
          createdItems.push(...result.items)
          if (!firstItem) firstItem = result.items[0]
        }
      } else if (gradeSizes.value.length > 0) {
        // Only sizes (original behavior)
        creating = true
        const result = await inventoryAPI.createGrade({ ...baseGradePayload, color: form.color || null })
        creating = false
        createdItems.push(...result.items)
        firstItem = result.items[0]
      } else {
        // Only colors — create one item per color
        const baseSinglePayload = {
          ...form,
          supplier_id: form.supplier_id || null,
          image_data: form.image_data || null,
          brand: form.brand || null,
          size: form.size.trim().toUpperCase(),
          barcode: form.barcode ? form.barcode + form.size.trim().toUpperCase() : '',
          group_key: sharedGroupKey,
        }
        for (const color of gradeColors.value) {
          creating = true
          const result = await inventoryAPI.createItem({ ...baseSinglePayload, color })
          creating = false
          createdItems.push(result)
          if (gradeInitialStock.value > 0) {
            await inventoryAPI.createMovement({
              item_id: result.id,
              movement_type: 'entry',
              quantity: gradeInitialStock.value,
              reason: 'Estoque inicial',
              location: stockLocation.value,
            })
          }
          if (!firstItem) firstItem = result
        }
      }

      emit('saved', firstItem!)
      return
    }

    // ── Single item ───────────────────────────────────────────────────────────
    const payload = {
      ...form,
      supplier_id: form.supplier_id || null,
      image_data: form.image_data || null,
      brand: form.brand || null,
      group_key: form.group_key || null,
    }
    let result: InventoryItem
    if (isEdit.value && props.item) {
      result = await inventoryAPI.updateItem(props.item.id, payload)
    } else {
      creating = true
      result = await inventoryAPI.createItem(payload)
      creating = false
      createdItems.push(result)
      // Create initial stock movement if quantity > 0
      if (initialStock.value > 0) {
        await inventoryAPI.createMovement({
          item_id: result.id,
          movement_type: 'entry',
          quantity: initialStock.value,
          reason: 'Estoque inicial',
          location: stockLocation.value,
        })
      }
    }
    emit('saved', result)
  } catch (e: any) {
    const detail = e.response?.data?.detail
    errors.name = typeof detail === 'string' ? detail : 'Erro ao salvar'
    partialItems.value = createdItems
    uncertainSave.value = creating && !e.response
    if (createdItems.length || uncertainSave.value) emit('partial', createdItems)
    activeTab.value = 'basic'
  } finally {
    saving.value = false
  }
}

function onBarcodeDetected(code: string) {
  form.barcode = code
  showScanner.value = false
}

// AI results may fill empty fields; competing evidence never overwrites a choice silently.
function currentIntake(): IntakeDraft {
  return { name: form.name, description: form.description, category: form.category, brand: form.brand,
    color: form.color, size: form.size, barcode: form.barcode,
    price: form.sale_price || priceEdited.value || isEdit.value ? `${form.sale_currency} ${form.sale_price}` : '' }
}
const priceEdited = ref(false)
watch(() => [form.sale_price, form.sale_currency], () => { priceEdited.value = true }, { flush: 'sync' })
watch(form, () => { intakeReviewed.value = false; reviewError.value = '' }, { deep: true, flush: 'sync' })
function applyIntake(data: IntakeDraft) {
  for (const field of ['name', 'description', 'brand', 'color', 'size', 'barcode'] as const) {
    if (data[field] !== undefined) form[field] = data[field]
  }
  if (data.category !== undefined) {
    const [parent, ...sub] = data.category.split('>')
    categorySub.value = sub.join('>')
    categoryParent.value = parentCategories.includes(parent) ? parent : '_custom'
    categoryCustom.value = data.category
    form.category = data.category
  }
  if (data.price) {
    const [currency, amount] = data.price.split(' ')
    form.sale_price = Number(amount); form.sale_currency = currency; form.currency = currency
  }
}
function addSuggestions(data: IntakeDraft, source: IntakeSource) {
  const merged = mergeIntake(currentIntake(), data, source, previousSuggestions[source])
  // New evidence supersedes pending suggestions from the same source, not the form.
  conflicts.value = conflicts.value.filter(c => c.source !== source || data[c.field] === previousSuggestions[source][c.field])
  applyIntake(merged.additions)
  for (const conflict of merged.conflicts) {
    conflicts.value = conflicts.value.filter(c => c.field !== conflict.field || c.source !== conflict.source)
    conflicts.value.push(conflict)
  }
  previousSuggestions[source] = { ...data }
  intakeReviewed.value = false
}
function resolveConflict(conflict: IntakeConflict, useSuggestion: boolean) {
  if (useSuggestion) applyIntake({ [conflict.field]: conflict.proposed })
  conflicts.value = conflicts.value.filter(c => c.field !== conflict.field)
  intakeReviewed.value = false
}
function onProductPhotoResult(result: ProductPhotoResult) {
  addSuggestions(result, 'photo')
  form.image_data = result.image_data
  reviewOriginal.value = result.original_image || ''
  photoAdded.value = true
  showProductPhoto.value = false
  activeTab.value = 'capture'
}
function onOcrResult(data: OcrAppliedFields) {
  addSuggestions({ name: data.name, brand: data.brand, size: data.size, color: data.color, barcode: data.barcode,
    price: data.sale_price != null && data.currency ? `${data.currency} ${data.sale_price}` : undefined }, 'label')
  labelAdded.value = true
  showOcr.value = false
  activeTab.value = 'capture'
}
function continueToStock() {
  if (conflicts.value.length || !intakeReviewed.value) {
    reviewError.value = 'Confira os dados e resolva as diferenças antes de continuar.'
    if (conflicts.value.length) conflictsPanel.value?.querySelector('button')?.focus()
    else reviewInput.value?.focus()
    return
  }
  if (!validate()) { nameInput.value?.focus(); return }
  activeTab.value = 'stock'
}

// Photo handling
function onPhotoFile(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  resizeAndStore(file)
}

function resizeAndStore(source: File | HTMLCanvasElement) {
  if (source instanceof File) {
    const reader = new FileReader()
    reader.onload = (ev) => {
      const img = new Image()
      img.onload = () => { storeResized(img) }
      img.src = ev.target?.result as string
    }
    reader.readAsDataURL(source)
  } else {
    // source is already a canvas
    form.image_data = source.toDataURL('image/jpeg', 0.82)
  }
}

function storeResized(img: HTMLImageElement) {
  const MAX = 400
  const scale = Math.min(MAX / img.width, MAX / img.height, 1)
  const w = Math.round(img.width * scale)
  const h = Math.round(img.height * scale)
  const canvas = document.createElement('canvas')
  canvas.width = w; canvas.height = h
  canvas.getContext('2d')!.drawImage(img, 0, 0, w, h)
  form.image_data = canvas.toDataURL('image/jpeg', 0.82)
  activeTab.value = 'photo'
}

async function stopCameraPhoto() {
  if (photoStream) { photoStream.getTracks().forEach(t => t.stop()); photoStream = null }
  showCameraPhoto.value = false
}

watch(showCameraPhoto, async (val) => {
  if (!val) return
  try {
    photoStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
    if (photoVideoRef.value) photoVideoRef.value.srcObject = photoStream
  } catch {
    showCameraPhoto.value = false
  }
})

function capturePhoto() {
  const video = photoVideoRef.value
  if (!video) return
  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth; canvas.height = video.videoHeight
  canvas.getContext('2d')!.drawImage(video, 0, 0)
  stopCameraPhoto()
  storeResized(new Image())
  // Use canvas directly
  const MAX = 400
  const scale = Math.min(MAX / canvas.width, MAX / canvas.height, 1)
  const w = Math.round(canvas.width * scale)
  const h = Math.round(canvas.height * scale)
  const out = document.createElement('canvas')
  out.width = w; out.height = h
  out.getContext('2d')!.drawImage(canvas, 0, 0, w, h)
  form.image_data = out.toDataURL('image/jpeg', 0.82)
  activeTab.value = 'photo'
}
function handleComma(event: KeyboardEvent, add: () => void) {
  if (event.key === ',') {
    event.preventDefault()
    add()
  }
}
</script>

<style scoped>
.variant-entry { padding:12px; }
.variant-entry p { margin:0 0 10px; font-size:.85rem; color:#64748b; }
.variant-actions { display:flex; flex-wrap:wrap; gap:8px; }

.modal-container.intake-modal { max-width: 680px; }
.intake-modal .tabs .tab { min-width: 0; padding: .8rem .45rem; font-size: .82rem; }
.intake-hint { margin: 0; font-size: .83rem; line-height: 1.5; color: #64748b; }
.intake-sources { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
.intake-source { display: flex; flex-direction: column; align-items: flex-start; gap: .65rem; padding: 1rem; border: 1px solid #dbe3ef; border-radius: 12px; background: #f8fafc; min-width: 0; }
.intake-source h3 { font-size: .95rem; margin: 0; }
.intake-source small { display: block; color: #64748b; font-size: .7rem; font-weight: 400; margin-top: .2rem; }
.intake-source p { font-size: .8rem; line-height: 1.5; color: #64748b; margin: 0; flex: 1; }
.intake-source-icon { font-size: 1.8rem; }
.intake-photo-actions { display: flex; flex-wrap: wrap; gap: .5rem; width: 100%; }
.intake-photo-actions .erp-button { max-width: 100%; white-space: normal; height: auto; }
.intake-thumbnail { height: 86px; width: 86px; object-fit: contain; border-radius: 8px; background: white; }
.intake-ready { color: #15803d; font-size: .75rem; }
.intake-review-heading { display: flex; align-items: flex-start; gap: 1rem; }
.intake-review-heading .erp-button { flex-shrink: 0; }
.intake-images { display: flex; align-items: center; flex-wrap: wrap; gap: 1rem; }
.intake-images figure { margin: 0; }
.intake-images img { width: 125px; height: 125px; object-fit: contain; border: 1px solid #e2e8f0; border-radius: 8px; }
.intake-images figcaption { font-size: .7rem; text-align: center; color: #64748b; }
.intake-details { margin-top: 1rem; }
.intake-conflicts { border: 1px solid #fcd34d; border-radius: 10px; background: #fffbeb; padding: 1rem; }
.intake-conflicts h3 { font-size: .9rem; margin: 0; color: #92400e; }
.intake-conflicts p { font-size: .8rem; line-height: 1.5; color: #92400e; }
.intake-conflict { display: flex; flex-direction: column; gap: .5rem; margin-top: 1rem; min-width: 0; }
.intake-conflict strong { font-size: .8rem; }
.intake-conflict .erp-button { justify-content: flex-start; text-align: left; white-space: normal; overflow-wrap: anywhere; height: auto; }
.intake-conflict-note { background: #fffbeb; border-radius: 8px; padding: .8rem; color: #92400e; font-size: .82rem; line-height: 1.5; }
.intake-review-check { display: flex; align-items: flex-start; gap: .6rem; background: #eff6ff; padding: .85rem; border-radius: 8px; font-size: .85rem; margin-top: 1.2rem; }
.intake-review-check input { accent-color: #2563eb; margin-top: .2rem; flex-shrink: 0; }
.intake-stock-summary { display: flex; gap: 1rem; padding: .8rem; background: #f8fafc; border-radius: 10px; }
.intake-stock-summary img { width: 64px; height: 64px; object-fit: contain; }
.intake-stock-summary p { margin: .25rem 0; font-size: .8rem; color: #64748b; }
.intake-grade { margin-top: 1rem; border: 1px solid #dbe3ef; border-radius: 10px; padding: .9rem; }
.intake-grade-toggle { margin-top: 1rem; }
.intake-grade h3 { margin: 0; cursor: pointer; color: #334155; font-size: .85rem; font-weight: 600; }
.intake-grade .tab-content { margin-top: 1rem; }
.intake-total { border-top: 1px solid #e2e8f0; padding: .8rem 1.25rem; font-size: .8rem; color: #475569; background: #f8fafc; }
@media (max-width: 480px) {
  .intake-modal .tabs .tab { font-size: .75rem; padding: .75rem .3rem; }
  .intake-sources { grid-template-columns: 1fr; gap: .75rem; }
  .intake-source { gap: .5rem; padding: .85rem; }
  .intake-source-icon { font-size: 1.5rem; }
  .intake-review-heading { flex-direction: column; gap: .65rem; }
  .intake-modal .modal-footer { gap: .5rem; padding: .85rem; }
  .intake-modal .modal-footer .erp-button { font-size: .8rem; padding-inline: .75rem; white-space: normal; }
}

.stock-readout { margin-bottom: 1rem; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; }
.stock-readout-values { display: flex; flex-wrap: wrap; gap: 1rem; padding: .75rem; font-size: .85rem; }
.stock-readout-warning { padding: .75rem; background: #fffbeb; color: #92400e; font-size: .85rem; }
.stock-readout-warning p { margin: .35rem 0 0; }
.partial-save-warning { padding: 1rem; margin-bottom: 1rem; border: 1px solid #f59e0b; border-radius: 8px; background: #fffbeb; color: #92400e; font-size: .85rem; }
.partial-save-warning p { margin: .5rem 0; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 500; display: flex; align-items: center; justify-content: center; padding: 1rem; }
.modal-container { background: white; border-radius: 12px; width: 100%; max-width: 520px; max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 1rem 1.25rem; border-bottom: 1px solid #e5e7eb; }
.modal-header h2 { margin: 0; font-size: 1.1rem; font-weight: 600; }
.close-btn { background: none; border: none; cursor: pointer; color: #6b7280; }
.tabs { display: flex; border-bottom: 1px solid #e5e7eb; }
.tab { flex: 1; padding: 0.75rem; background: none; border: none; cursor: pointer; font-size: 0.9rem; color: #6b7280; border-bottom: 2px solid transparent; position: relative; }
.tab.active { color: #3b82f6; border-bottom-color: #3b82f6; font-weight: 600; }
.tab-dot { width: 6px; height: 6px; background: #10b981; border-radius: 50%; display: inline-block; margin-left: 4px; vertical-align: middle; }
.modal-body { flex: 1; overflow-y: auto; padding: 1.25rem; }
.tab-content { display: flex; flex-direction: column; gap: 1rem; }
.form-group { display: flex; flex-direction: column; gap: 0.25rem; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.form-group label { font-size: 0.8rem; font-weight: 500; color: #374151; display: flex; align-items: center; gap: 0.35rem; }
.auto-tag { font-size: 0.65rem; background: #dbeafe; color: #1d4ed8; border-radius: 4px; padding: 0.1rem 0.35rem; }
.form-input { padding: 0.5rem 0.75rem; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.9rem; outline: none; width: 100%; box-sizing: border-box; }
.price-with-currency { display: flex; gap: 0; }
.currency-select { padding: 0.5rem 0.4rem; border: 1px solid #d1d5db; border-right: none; border-radius: 6px 0 0 6px; font-size: 0.8rem; font-weight: 600; color: #374151; background: #f9fafb; outline: none; cursor: pointer; flex-shrink: 0; }
.currency-select:focus { border-color: #3b82f6; }
.price-input { border-radius: 0 6px 6px 0 !important; }
.form-input:focus { border-color: #3b82f6; }
.form-input.error { border-color: #ef4444; }
.error-msg { font-size: 0.75rem; color: #ef4444; }
.warn-msg { font-size: 0.75rem; color: #f59e0b; }
.input-combo { display: flex; gap: 0.5rem; }
.input-combo .form-input { flex: 1; }
.combo-toggle { padding: 0 0.75rem; background: #f3f4f6; border: 1px solid #d1d5db; border-radius: 6px; cursor: pointer; font-size: 1rem; }
.barcode-row { display: flex; gap: 0.5rem; }
.barcode-row .form-input { flex: 1; }
.scan-btn { padding: 0.5rem 0.75rem; background: #f3f4f6; border: 1px solid #d1d5db; border-radius: 6px; cursor: pointer; color: #374151; }
/* Photo tab */
.photo-preview { display: flex; flex-direction: column; align-items: center; gap: 0.75rem; }
.item-photo { width: 100%; max-height: 260px; object-fit: contain; border-radius: 8px; border: 1px solid #e5e7eb; }
.remove-photo { background: none; border: none; color: #ef4444; cursor: pointer; font-size: 0.85rem; }
.photo-placeholder { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; padding: 2rem; color: #9ca3af; border: 2px dashed #e5e7eb; border-radius: 10px; }
.photo-icon { color: #d1d5db; }
.photo-actions { display: flex; gap: 0.75rem; }
.hidden-input { display: none; }
.inline-camera { margin-top: 0.75rem; border-radius: 8px; overflow: hidden; }
.inline-video { width: 100%; display: block; }
.inline-camera-btns { display: flex; gap: 0.5rem; padding: 0.75rem; background: #f9fafb; }
.photo-hint { font-size: 0.72rem; color: #9ca3af; }
.modal-footer { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 0.75rem; padding: 1rem 1.25rem; border-top: 1px solid #e5e7eb; }
.delete-product { margin-right: auto; }
@media(max-width: 480px) { .delete-product { flex-basis: 100%; } }
.btn { display: flex; align-items: center; gap: 0.4rem; padding: 0.5rem 1.25rem; border-radius: 6px; font-size: 0.9rem; cursor: pointer; border: none; font-weight: 500; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: #f3f4f6; color: #374151; border: 1px solid #d1d5db; }
.field-hint { font-size: 0.7rem; color: #9ca3af; margin-top: 0.15rem; }
.form-hint { font-size: 0.72rem; color: #9ca3af; }
.loc-toggle { display: flex; gap: 0.5rem; }
.loc-btn { flex: 1; padding: 0.45rem 0; border: 2px solid #e5e7eb; border-radius: 8px; cursor: pointer; background: white; font-size: 0.85rem; font-weight: 500; transition: all 0.15s; }
.loc-btn.active { background: #dbeafe; border-color: #3b82f6; color: #1d4ed8; }

/* ── Grade Tab ─────────────────────────────────────────────────────────────── */
.tab-badge {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 16px; height: 16px; padding: 0 4px;
  background: #3b82f6; color: white; border-radius: 99px;
  font-size: 0.6rem; font-weight: 700; margin-left: 4px; vertical-align: middle;
}

.grade-banner {
  display: flex; align-items: flex-start; gap: 0.5rem;
  background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px;
  padding: 0.65rem 0.75rem; color: #1d4ed8;
}
.grade-banner p { margin: 0; font-size: 0.8rem; line-height: 1.4; }

.grade-presets {
  display: flex; flex-wrap: wrap; gap: 0.4rem;
}
.grade-options-heading { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: .5rem; margin-bottom: .5rem; }
.grade-options-heading h3 { margin: 0; }
.preset-btn {
  padding: 0.3rem 0.7rem; border: 1px solid #d1d5db; border-radius: 99px;
  background: white; color: #374151; font-size: 0.78rem; font-weight: 500;
  cursor: pointer; transition: all 0.15s; white-space: nowrap;
}
.preset-btn:hover { border-color: #3b82f6; color: #3b82f6; background: #eff6ff; }
.preset-btn.active { background: #3b82f6; border-color: #3b82f6; color: white; }
.preset-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.preset-add-btn { padding: 0.3rem 0.6rem; font-size: 1rem; font-weight: 700; line-height: 1; border-style: dashed; color: #6b7280; }
.preset-add-btn:hover { border-color: #10b981; color: #10b981; background: #ecfdf5; }
.preset-add-btn.active { background: #ecfdf5; border-color: #10b981; color: #059669; border-style: solid; }
.preset-option, .color-option { display: inline-flex; max-width: 100%; }
.preset-option .preset-btn { white-space: normal; overflow-wrap: anywhere; }
.color-option .quick-color-btn { overflow-wrap: anywhere; }
.preset-option:has(.option-remove) .preset-btn, .color-option:has(.option-remove) .quick-color-btn { border-radius: 99px 0 0 99px; }
.option-remove { border: 1px solid #d1d5db; border-left: 0; border-radius: 0 99px 99px 0; background: white; color: #64748b; padding: 0 .55rem; min-width: 32px; cursor: pointer; }
.option-remove:hover { color: #dc2626; background: #fef2f2; }
.choice-editor { border: 1px solid #c7d2fe; border-radius: 8px; background: #f8fafc; padding: .5rem; }
.new-preset-form { margin-top: .6rem; display: flex; flex-direction: column; gap: .5rem; }
.new-preset-form label { display: flex; flex-direction: column; align-items: stretch; }
.choice-editor-actions, .preset-size-preview { display: flex; align-items: center; flex-wrap: wrap; gap: .4rem; }
.choice-editor-actions { flex-shrink: 0; }

.size-count { font-size: 0.72rem; color: #6b7280; font-weight: 400; }

.grade-chips {
  display: flex; flex-wrap: wrap; gap: 0.35rem; align-items: center;
  border: 1px solid #d1d5db; border-radius: 8px; padding: 0.4rem 0.5rem;
  min-height: 42px; cursor: text; background: white; transition: border-color 0.15s;
}
.grade-chips:focus-within { border-color: #3b82f6; }

.grade-chip {
  display: inline-flex; align-items: center; gap: 3px;
  background: #e0e7ff; color: #3730a3; border-radius: 99px;
  padding: 0.15rem 0.5rem 0.15rem 0.6rem; font-size: 0.8rem; font-weight: 600;
}
.chip-x {
  background: none; border: none; cursor: pointer; color: #6366f1;
  font-size: 1rem; line-height: 1; padding: 0; display: flex; align-items: center;
  transition: color 0.1s;
}
.chip-x:hover { color: #ef4444; }

.chip-input {
  border: none; outline: none; font-size: 0.85rem; min-width: 70px;
  flex: 1; padding: 0.1rem 0.2rem; background: transparent;
}

.grade-barcode-hint {
  display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;
  background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;
  padding: 0.5rem 0.65rem; font-size: 0.78rem; color: #475569;
}
.hint-label { font-weight: 500; }
.hint-code { background: #e2e8f0; border-radius: 3px; padding: 0.1rem 0.35rem; font-size: 0.78rem; }
.hint-arrow { color: #9ca3af; }
.hint-etc { color: #9ca3af; font-size: 0.7rem; }

.grade-preview {
  border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;
  max-height: 200px; overflow-y: auto;
}
.gp-row {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.35rem 0.65rem; font-size: 0.8rem;
  border-bottom: 1px solid #f3f4f6;
}
.gp-row:last-child { border-bottom: none; }
.gp-row:nth-child(even) { background: #f9fafb; }
.gp-size {
  width: 40px; flex-shrink: 0; font-weight: 700; color: #4f46e5;
  background: #e0e7ff; border-radius: 4px; padding: 0.1rem 0.3rem;
  text-align: center; font-size: 0.75rem;
}
.gp-name { flex: 1; color: #111827; }
.gp-barcode { font-family: monospace; font-size: 0.72rem; color: #9ca3af; flex-shrink: 0; }

/* Add-size row */
.add-size-row {
  display: flex; gap: 0.4rem; margin-top: 0.35rem;
}
.add-size-input { font-size: 0.82rem !important; }
.btn-add-chip {
  flex-shrink: 0; padding: 0.45rem 0.75rem; background: #f0f9ff; border: 1px solid #bae6fd;
  border-radius: 6px; color: #0369a1; font-size: 0.8rem; font-weight: 600; cursor: pointer; white-space: nowrap;
}
.btn-add-chip:hover { background: #e0f2fe; }

/* Quick color buttons */
.quick-colors {
  display: flex; align-items: center; flex-wrap: wrap; gap: 0.35rem; margin-bottom: 0.4rem;
}
.quick-color-btn {
  padding: 0.25rem 0.7rem; border: 1.5px solid #d1d5db; border-radius: 99px;
  background: white; font-size: 0.78rem; font-weight: 500; color: #374151; cursor: pointer;
  transition: all 0.15s;
}
.quick-color-btn:hover { border-color: #6366f1; color: #4f46e5; }
.quick-color-btn.active { background: #e0e7ff; border-color: #6366f1; color: #4338ca; font-weight: 700; cursor: default; }
.quick-check { font-size: 0.7rem; margin-right: 1px; }
.quick-color-add { min-width: 32px; font-weight: 700; }
.quick-color-entry { display: inline-flex; flex-wrap: wrap; align-items: center; gap: .3rem; max-width: 100%; box-sizing: border-box; }
.quick-color-entry:focus-within { outline: 2px solid #c7d2fe; outline-offset: 1px; }
.quick-color-entry input { flex: 1 1 auto; min-width: 100px; max-width: 100%; border: 0; padding: .3rem; outline: 0; background: transparent; color: #374151; font: inherit; font-size: .85rem; }
.selected-colors { display: flex; flex-wrap: wrap; gap: .35rem; margin-bottom: .4rem; }

/* Color chips (slightly different from size chips) */
.grade-chip-color {
  background: #fce7f3; color: #9d174d;
}

/* Color badge in preview */
.gp-color-badge {
  font-size: 0.7rem; font-weight: 700; background: #fce7f3; color: #9d174d;
  border-radius: 4px; padding: 0.1rem 0.4rem; flex-shrink: 0;
}

.grade-empty {
  text-align: center; color: #9ca3af; font-size: 0.85rem; padding: 1.5rem;
  border: 2px dashed #e5e7eb; border-radius: 8px;
}
</style>
