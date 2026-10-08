<template>
  <div class="inventory-view">
    <div class="sticky-toolbar">
      <div class="mobile-toolbar-bar">
        <button type="button" class="erp-button erp-button--ghost erp-button--icon" :aria-label="tr('Voltar ao dashboard')" @click="$router.replace('/dashboard')">←</button>
        <div class="mobile-toolbar-title"><strong>{{ tr('Estoque') }}</strong><span v-if="hasActiveFilters">{{ tr('Filtros ativos') }}</span></div>
        <button type="button" class="erp-button erp-button--secondary erp-button--sm mobile-toolbar-toggle"
          :aria-expanded="mobileToolbarOpen" aria-controls="inventory-toolbar-panel" @click="toggleMobileToolbar">
          {{ tr(mobileToolbarOpen ? 'Recolher' : 'Filtros e ações') }}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true" :class="{ expanded: mobileToolbarOpen }"><path d="m6 9 6 6 6-6" /></svg>
        </button>
      </div>
      <div id="inventory-toolbar-panel" class="inventory-toolbar-panel" :class="{ 'mobile-collapsed': !mobileToolbarOpen }">
    <ModuleHeader :title="tr('Estoque')">
      <button v-if="auth.isOwner" class="erp-button erp-button--secondary erp-button--sm" @click="showDeletedHistory = true">{{ tr('Histórico de excluídos') }}</button>
      <button
        @click="showDiagnostics = !showDiagnostics"
        class="btn btn-secondary diagnostics-toggle erp-button erp-button--secondary erp-button--sm"
        :aria-expanded="showDiagnostics"
        aria-controls="inventory-diagnostics"
      >
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16" aria-hidden="true">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M9 12l2 2 4-4M9 4H5v16h14V4h-4M9 3h6v4H9z"
          />
        </svg>
        {{ diagnosticsText("open") }}
      </button>
      <button
        @click="showLabelTemplates = true"
        class="btn btn-secondary btn-modelos-ia-desktop erp-button erp-button--secondary erp-button--sm"
      >
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
          />
        </svg>
        {{ tr("Exemplos de etiquetas") }}
      </button>
      <button @click="showImport = true" class="btn btn-secondary erp-button erp-button--secondary erp-button--sm">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
          />
        </svg>
        {{ tr("Importar") }}
      </button>
      <button @click="openCreate" class="btn btn-primary erp-button erp-button--primary erp-button--sm">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
        </svg>
        {{ tr("Novo item") }}
      </button>
    </ModuleHeader>

    <!-- Search + Camera -->
    <div class="search-section">
      <div class="search-row">
        <div class="search-box">
          <svg class="search-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input v-model="searchQuery" type="text" :placeholder="tr('Produto, marca, tamanho ou código...')" class="search-input" :class="{ 'search-input-clearable': searchQuery }" />
          <button v-if="searchQuery" @click="clearSearch()" class="search-clear-btn erp-button erp-button--ghost erp-button--icon" :title="tr('Limpar busca')" type="button">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="14" height="14"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <button @click="showScanner = true" class="camera-btn erp-button erp-button--ghost erp-button--icon" :title="tr('Escanear código')">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>
      </div>

      <!-- Filter chips (status + marca + categoria + ver grupos) -->
      <div class="filter-chips" ref="filterChipsRef">
        <!-- Status -->
        <button class="erp-control"
          v-for="chip in statusChips"
          :key="chip.value"
          @click="setStatusFilter(chip.value)"
          :class="['chip', { active: activeStatus === chip.value, 'chip-inactive': chip.value === 'inactive' }]"
        >
          {{ tr(chip.label) }}
          <span v-if="chip.count !== undefined" class="chip-count">{{ chip.count }}</span>
        </button>

        <!-- Marca dropdown chip -->
        <div class="chip-dd-wrap" v-if="distinctBrands.length > 0">
          <button class="erp-control" @click="toggleFilter('brand')" :class="['chip', { active: !!filterBrand }]">
            {{ filterBrand || tr('Marca') }} <span class="chip-caret">▾</span>
          </button>
          <div v-if="openFilter === 'brand'" class="chip-dropdown">
            <div class="chip-dd-search-wrap">
              <input v-model="brandSearch" class="chip-dd-search" :placeholder="tr('Buscar marca...')" @click.stop type="text" autocomplete="off" />
            </div>
            <button class="erp-control" @click="setFilter('brand', '')" :class="['chip-dd-opt', { active: !filterBrand }]">{{ tr('Todas as marcas') }}</button>
            <button class="erp-control" v-for="b in filteredBrands" :key="b" @click="setFilter('brand', b)" :class="['chip-dd-opt', { active: filterBrand === b }]">{{ b }}</button>
          </div>
        </div>

        <!-- Categoria dropdown chip -->
        <div class="chip-dd-wrap" v-if="distinctCategories.length > 0">
          <button class="erp-control" @click="toggleFilter('category')" :class="['chip', { active: !!filterCategory }]">
            {{ filterCategory ? formatCategory(filterCategory) : tr('Categoria') }} <span class="chip-caret">▾</span>
          </button>
          <div v-if="openFilter === 'category'" class="chip-dropdown">
            <div class="chip-dd-search-wrap">
              <input v-model="categorySearch" class="chip-dd-search" :placeholder="tr('Buscar categoria...')" @click.stop type="text" autocomplete="off" />
            </div>
            <button class="erp-control" @click="setFilter('category', '')" :class="['chip-dd-opt', { active: !filterCategory }]">{{ tr('Todas as categorias') }}</button>
            <button class="erp-control" v-for="c in filteredCategories" :key="c" @click="setFilter('category', c)" :class="['chip-dd-opt', { active: filterCategory === c }]">{{ formatCategory(c) }}</button>
          </div>
        </div>

        <!-- Location chips -->
        <button class="erp-control" @click="setLocationFilter('loja')" :class="['chip', 'chip-loc', { active: filterLocation === 'loja' }]">
          {{ tr('Loja') }}
          <span v-if="inventoryStore.alerts?.loja_count !== undefined" class="chip-count">{{ inventoryStore.alerts.loja_count }}</span>
        </button>
        <button class="erp-control" @click="setLocationFilter('deposito')" :class="['chip', 'chip-loc', { active: filterLocation === 'deposito' }]">
          {{ tr('Depósito') }}
          <span v-if="inventoryStore.alerts?.deposito_count !== undefined" class="chip-count">{{ inventoryStore.alerts.deposito_count }}</span>
        </button>

        <!-- Ver grades (só aparece se existem grupos) -->
        <button class="erp-control" v-if="hasGroups" @click="toggleGroupMode" :class="['chip', { active: groupMode }]">
          {{ tr('Ver grades') }}
          <span v-if="inventoryStore.alerts?.group_count" class="chip-count">{{ inventoryStore.alerts.group_count }}</span>
          <span v-if="groupMode" class="chip-check">✓</span>
        </button>
      </div>

      <!-- Sugestões de agrupamento (visível no modo seleção) -->
      <div v-if="selectionMode && suggestedGroups.length > 0" class="suggestions-bar">
        <span class="sug-label">{{ tr('Similares detectados:') }}</span>
        <button
          v-for="sg in suggestedGroups.slice(0, 4)"
          :key="sg.name"
          @click="selectSuggestedGroup(sg)"
          class="sug-chip erp-control"
          :title="tr('{count} itens com nome similar', { count: sg.items.length })"
        >
          {{ sg.name }} ({{ sg.items.length }})
        </button>
      </div>

      <!-- Inventory summary stats -->
      <div v-if="inventoryStore.alerts" class="inv-stats">
        <span class="inv-stat">
          <span class="inv-stat-num">{{ inventoryStore.alerts.total_active_items }}</span>
          <span class="inv-stat-label">{{ tr('itens') }}</span>
        </span>
        <span class="inv-stat-sep">·</span>
        <span class="inv-stat">
          <span class="inv-stat-num">{{ inventoryStore.alerts.group_count }}</span>
          <span class="inv-stat-label">{{ tr('grades') }}</span>
        </span>
        <span class="inv-stat-sep">·</span>
        <button
          class="inv-stat inv-stat-btn erp-control"
          :class="{ 'inv-stat-btn-active': filterUngroupedOnly }"
          @click="toggleUngroupedFilter"
          :title="tr('Filtrar itens sem grade')"
        >
          <span class="inv-stat-num">{{ inventoryStore.alerts.total_active_items - inventoryStore.alerts.grouped_items_count }}</span>
          <span class="inv-stat-label">{{ tr('sem grade') }}</span>
        </button>
        <template v-if="inventoryStore.alerts.low_stock_count > 0">
          <span class="inv-stat-sep">·</span>
          <button
            class="inv-stat inv-stat-btn inv-stat-warn erp-control"
            :class="{ 'inv-stat-btn-active inv-stat-warn-active': activeStatus === 'low_stock' }"
            @click="setStatusFilter(activeStatus === 'low_stock' ? '' : 'low_stock')"
            :title="tr('Filtrar estoque baixo')"
          >
            <span class="inv-stat-num">{{ inventoryStore.alerts.low_stock_count }}</span>
            <span class="inv-stat-label">{{ tr('baixo') }}</span>
          </button>
        </template>
        <template v-if="inventoryStore.alerts.out_of_stock_count > 0">
          <span class="inv-stat-sep">·</span>
          <button
            class="inv-stat inv-stat-btn inv-stat-danger erp-control"
            :class="{ 'inv-stat-btn-active inv-stat-danger-active': activeStatus === 'out_of_stock' }"
            @click="setStatusFilter(activeStatus === 'out_of_stock' ? '' : 'out_of_stock')"
            :title="tr('Filtrar sem estoque')"
          >
            <span class="inv-stat-num">{{ inventoryStore.alerts.out_of_stock_count }}</span>
            <span class="inv-stat-label">{{ tr('sem estoque') }}</span>
          </button>
        </template>
      </div>

      <!-- View mode switcher -->
      <div class="view-switcher">
        <span class="view-label">{{ tr('Visualização:') }}</span>
        <button class="erp-control" :class="['view-btn', { active: viewMode === 'list' }]" @click="setView('list')" :title="tr('Lista')">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
          </svg>
          {{ tr('Lista') }}
        </button>
        <button class="erp-control" :class="['view-btn', { active: viewMode === 'compact' }]" @click="setView('compact')" :title="tr('Compacto')">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 5h7M4 12h7M4 19h7M14 5h6M14 12h6M14 19h6" />
          </svg>
          {{ tr('Compacto') }}
        </button>
        <button class="erp-control" :class="['view-btn', { active: viewMode === 'grid' }]" @click="setView('grid')" :title="tr('Quadrados')">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
          </svg>
          {{ tr('Quadrados') }}
        </button>
        <span class="view-sep">|</span>
        <button class="erp-control" :class="['view-btn', { active: selectionMode }]" @click="toggleSelectionMode" :title="tr('Selecionar itens')" :aria-pressed="selectionMode">
          {{ tr('Selecionar') }}
        </button>
      </div>
    </div>
      </div><!-- /inventory-toolbar-panel -->
    </div><!-- /sticky-toolbar -->

    <InventoryDiagnosticsPanel
      v-if="showDiagnostics"
      :revision="diagnosticsRevision"
      :opening-id="diagnosticsOpeningId"
      :open-error="diagnosticsOpenError"
      @close="showDiagnostics = false"
      @open-item="openDiagnosticItem"
    />

    <div v-if="inventoryStore.error" class="list-load-error" role="alert">
      <div>
        <strong>{{ tr('Não foi possível carregar a lista de produtos.') }}</strong>
        <p>{{ tr('Os dados do estoque não foram confirmados. Tente novamente ou abra a conferência de estoque.') }}</p>
      </div>
      <button @click="reloadItems()" class="btn btn-secondary erp-button erp-button--secondary" :disabled="inventoryStore.loading">{{ tr('Tentar novamente') }}</button>
    </div>

    <!-- Loading -->
    <div v-if="inventoryStore.loading && flatList.length === 0" class="loading-state">
      <div class="spinner"></div>
      <p>{{ tr('Carregando itens...') }}</p>
    </div>

    <!-- Empty state -->
    <div v-else-if="!inventoryStore.loading && !inventoryStore.error && flatList.length === 0" class="empty-state">
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="48" height="48">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
      </svg>
      <p>{{ tr('Nenhum item encontrado') }}</p>
      <button v-if="hasActiveFilters" @click="clearItemFilters" class="btn btn-secondary erp-button erp-button--secondary" style="margin-top:1rem;">{{ tr('Limpar Filtros') }}</button>
      <button v-else @click="openCreate" class="btn btn-primary erp-button erp-button--primary" style="margin-top:1rem;">{{ tr('Novo item') }}</button>
    </div>

    <!-- Items list -->
    <div v-else-if="flatList.length > 0" ref="itemsContainer" class="items-container" :class="[`view-${viewMode}`, { 'drag-selecting': isDragSelecting }]">
      <svg v-if="!groupMode && gradeConnections.length" class="grade-connections" aria-hidden="true">
        <path v-for="connection in gradeConnections" :key="connection.id" :d="connection.path" />
      </svg>
      <template v-for="entry in flatList" :key="entry.type === 'group' ? 'g-' + entry.group.group_key : entry.item.id">

        <!-- ── CARD DE GRUPO ── -->
        <div v-if="entry.type === 'group'" class="group-card" :class="'alert-' + groupAlertLevel(entry.group.items)" @click="toggleExpand(entry.group.group_key)">
          <div class="group-header">
            <!-- Imagem do grupo (primeira imagem disponível) -->
            <div
              class="group-thumb-wrap"
              @click.stop="entry.group.items.find(i => i.image_data)?.image_data && (imageModalSrc = entry.group.items.find(i => i.image_data)!.image_data!)"
              :class="{ 'thumb-clickable': entry.group.items.some(i => i.image_data) }"
            >
              <img
                v-if="entry.group.items.find(i => i.image_data)"
                :src="entry.group.items.find(i => i.image_data)?.image_data || undefined"
                alt=""
                class="group-thumb"
              />
              <div v-else class="group-thumb-placeholder">
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="14" height="14"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" /></svg>
              </div>
            </div>
            <div class="group-title-area">
              <input
                v-if="editingGroupKey === entry.group.group_key"
                v-model="editingGroupName"
                class="group-name-input"
                @keydown.enter.prevent="saveGroupName(entry.group.group_key)"
                @keydown.escape="editingGroupKey = null"
                @blur="saveGroupName(entry.group.group_key)"
                @click.stop
              />
              <span
                v-else
                class="group-name group-name-editable"
                @click.stop="startEditGroupName(entry.group.group_key)"
                :title="tr('Clique para renomear o grupo')"
              >{{ groupTitle(entry.group.group_key) }} <svg class="edit-pencil" fill="none" viewBox="0 0 24 24" stroke="currentColor" width="11" height="11"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg></span>
              <span class="group-total-stock" :title="entry.group.total_stock === null ? tr('Não informado') : undefined">{{ tr('Total:') }} {{ displayStock(entry.group.total_stock) }}</span>
              <span v-if="groupAlertLevel(entry.group.items) === 'unknown'" class="alert-badge badge-unknown">{{ tr('Revisar estoque') }}</span>
              <span
                v-if="groupLocationBadge(entry.group.items) === 'deposito'"
                class="group-loc-badge badge-deposito"
              >{{ tr('Depósito') }}</span>
              <span
                v-else-if="groupLocationBadge(entry.group.items) === 'mixed'"
                class="group-loc-badge badge-mixed"
              >{{ tr('Loja + Dep.') }}</span>
              <span v-if="entry.group.items.find(i => i.barcode)" class="group-barcode">
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="9" height="9"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9V5a2 2 0 012-2h2M3 15v4a2 2 0 002 2h2m10-18h2a2 2 0 012 2v4m0 10v4a2 2 0 01-2 2h-2M9 3h6M9 21h6" /></svg>
                {{ entry.group.items.find(i => i.barcode)!.barcode }}
              </span>
            </div>
            <div class="group-btns">
              <button @click.stop="toggleExpand(entry.group.group_key)" class="action-btn expand-btn erp-button erp-button--ghost erp-button--icon" :title="expandedGroups.includes(entry.group.group_key) ? tr('Recolher') : tr('Expandir')">
                <svg class="expand-chevron" :class="{ 'chevron-open': expandedGroups.includes(entry.group.group_key) }" width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7"/>
                </svg>
              </button>
              <button @click.stop="handleUngroup(entry.group.group_key)" class="action-btn ungroup-btn erp-button erp-button--ghost erp-button--icon" :title="tr('Desagrupar')">
                <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7"/></svg>
              </button>
            </div>
          </div>
          <div class="size-chips">
            <span
              v-for="v in sortedByColorThenSize(entry.group.items)"
              :key="v.id"
              class="size-chip"
              :class="'chip-alert-' + stockAlertLevel(v)"
              :title="v.name + ' · ' + v.sku_internal"
            >
              <span class="chip-label" @click.stop="openEdit(v)">
                {{ v.size || v.name }}&nbsp;
                <template v-if="hasKnownStock(v) && v.stock_deposito > 0 && v.stock_loja > 0">{{ displayStock(v.stock_loja) }}|{{ displayStock(v.stock_deposito) }}</template>
                <template v-else>{{ displayStock(v.current_stock) }}</template>
                <span v-if="!hasKnownStock(v)" :title="tr('Revisar estoque')"> · {{ tr('Não informado') }}</span>
              </span>
              <div class="chip-remove-wrap">
                <button
                  class="chip-remove erp-button erp-button--danger erp-button--icon"
                  :title="tr('Remover do grupo')"
                  @click.stop="confirmRemoveChip = v.id"
                >×</button>
                <div v-if="confirmRemoveChip === v.id" class="chip-remove-confirm">
                  <span>{{ tr('Remover?') }}</span>
                  <button class="erp-button erp-button--danger" @click.stop="doRemoveFromGroup(v.id, entry.group.group_key)">{{ tr('Sim') }}</button>
                  <button class="erp-button erp-button--secondary" @click.stop="confirmRemoveChip = null">{{ tr('Não') }}</button>
                </div>
              </div>
            </span>
          </div>

          <!-- ── Itens expandidos (dentro do card, nunca invadem colunas adjacentes) ── -->
          <div v-if="expandedGroups.includes(entry.group.group_key)" class="group-exp-section" @click.stop>
            <div
              v-for="item in sortedByColorThenSize(entry.group.items)"
              :key="item.id"
              class="group-exp-row"
              :class="'exp-alert-' + stockAlertLevel(item)"
            >
              <div class="exp-left">
                <span class="exp-size">{{ item.size || item.name }}</span>
                <span v-if="item.color" class="exp-color">{{ item.color }}</span>
              </div>
              <div class="exp-stock-info">
                <span class="exp-stock-val">{{ tr('L:') }}{{ displayStock(item.stock_loja) }}</span>
                <span class="exp-stock-sep">·</span>
                <span class="exp-stock-val">{{ tr('D:') }}{{ displayStock(item.stock_deposito) }}</span>
                <span v-if="!hasKnownStock(item)" class="stock-unknown">{{ tr('Revisar estoque') }}</span>
              </div>
              <span v-if="Number(item.sale_price) > 0" class="exp-price">
                {{ currencySymbol(item.sale_currency || item.currency) }}&nbsp;{{ Number(item.sale_price).toLocaleString(numberLocale(), { minimumFractionDigits: 0 }) }}
              </span>
              <div class="exp-actions">
                <button @click.stop="openMovement(item)" :disabled="!hasKnownStock(item)" class="exp-btn exp-move erp-button erp-button--ghost erp-button--icon" :title="tr('Movimentar')">⇅</button>
                <button @click.stop="openEdit(item)" class="exp-btn exp-edit erp-button erp-button--ghost erp-button--icon" :title="tr('Editar')">✏</button>
              </div>
            </div>
          </div>
        </div>

        <!-- ── CARD INDIVIDUAL ── -->
        <div
          v-else
          class="item-card"
          :data-item-id="entry.item.id"
          :data-grade-key="entry.item.group_key || undefined"
          :class="['alert-' + stockAlertLevel(entry.item), { 'sub-item': groupMode && entry.item.group_key, 'card-selected': selectedIds.includes(entry.item.id), 'card-expanded': expandedCardIds.includes(entry.item.id) }]"
          @click="onCardClick(entry.item.id, $event)"
          @pointerdown="onItemPointerDown(entry.item.id, $event)"
        >
          <div v-if="!groupMode && entry.item.group_key" class="card-grade-label" :title="groupTitle(entry.item.group_key)">
            <span aria-hidden="true">↔</span> {{ tr('Grade {number}', { number: visibleGradeNumbers.get(entry.item.group_key)! }) }}
          </div>
          <!-- Checkbox de seleção -->
          <button v-if="selectionMode" type="button" class="card-check" :aria-label="tr('Selecionar {name}', { name: entry.item.name })" :aria-pressed="selectedIds.includes(entry.item.id)" @click.stop="toggleSelection(entry.item.id)">
            <span :class="['check-box', { checked: selectedIds.includes(entry.item.id), 'check-grouped': !!entry.item.group_key }]">
              <svg v-if="selectedIds.includes(entry.item.id)" fill="none" viewBox="0 0 24 24" stroke="currentColor" width="12" height="12"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/></svg>
            </span>
            <span v-if="groupMode && entry.item.group_key" class="in-group-badge" :title="tr('Já pertence ao grupo: {group}', { group: groupTitle(entry.item.group_key) })">{{ tr('grade') }}</span>
          </button>
          <!-- Imagem topo (grid view) -->
          <div class="item-grid-image" @click.stop="entry.item.image_data && (imageModalSrc = entry.item.image_data)" :class="{ 'thumb-clickable': entry.item.image_data }">
            <img v-if="entry.item.image_data" :src="entry.item.image_data" alt="" class="item-grid-img" />
            <div v-else class="item-grid-placeholder">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="28" height="28"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" /></svg>
            </div>
          </div>

          <!-- ── MODO LISTA: linha única ── -->
          <div v-if="viewMode === 'list'" class="item-list-row" :style="selectionMode ? 'padding-left:1.85rem' : ''">
            <div class="list-left">
              <span class="list-name" :class="'stock-' + stockAlertLevel(entry.item)">{{ entry.item.name }}</span>
              <template v-if="entry.item.color">
                <span class="list-sep">·</span><span class="list-attr">{{ entry.item.color }}</span>
              </template>
              <template v-if="entry.item.size">
                <span class="list-sep">·</span><span class="list-size-badge">{{ entry.item.size }}</span>
              </template>
              <template v-if="entry.item.brand">
                <span class="list-sep">·</span><span class="list-brand-tag">{{ entry.item.brand }}</span>
              </template>
              <template v-if="entry.item.category">
                <span class="list-sep">·</span><span class="list-attr list-cat-tag">{{ formatCategory(entry.item.category) }}</span>
              </template>
              <span class="list-sep list-sep-spaced">·</span>
              <span class="list-stock" :class="'stock-' + stockAlertLevel(entry.item)">
                {{ tr('L:') }}{{ displayStock(entry.item.stock_loja) }} {{ tr('D:') }}{{ displayStock(entry.item.stock_deposito) }}
                <span v-if="!hasKnownStock(entry.item)" class="stock-unknown"> · {{ tr('Revisar estoque') }}</span>
              </span>
              <template v-if="Number(entry.item.sale_price) > 0">
                <span class="list-sep">·</span>
                <span class="list-price">{{ currencySymbol(entry.item.sale_currency || entry.item.currency) }}&nbsp;{{ Number(entry.item.sale_price).toLocaleString(numberLocale(), { minimumFractionDigits: 2 }) }}</span>
              </template>
              <template v-if="entry.item.barcode">
                <span class="list-sep list-sep-subtle">·</span>
                <span class="list-barcode">{{ entry.item.barcode }}</span>
              </template>
            </div>
            <div class="list-actions">
              <button @click.stop="openMovement(entry.item)" :disabled="!hasKnownStock(entry.item)" class="action-btn move-btn list-btn erp-button erp-button--secondary erp-button--sm">{{ tr('Movimentar') }}</button>
              <button @click.stop="openEdit(entry.item)" class="action-btn edit-btn list-btn erp-button erp-button--secondary erp-button--sm">{{ tr('Editar') }}</button>
            </div>
          </div>

          <div class="item-row-main" v-show="viewMode !== 'list'">
            <!-- Thumb -->
            <div class="item-thumb-wrap" @click="entry.item.image_data && (imageModalSrc = entry.item.image_data)" :class="{ 'thumb-clickable': entry.item.image_data }">
              <img v-if="entry.item.image_data" :src="entry.item.image_data" alt="" class="item-thumb" />
              <div v-else class="item-thumb-placeholder"><svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="14" height="14"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" /></svg></div>
            </div>

            <div class="item-info">
              <div class="item-name-row">
                <span class="item-name">{{ entry.item.name }}</span>
                <span v-if="entry.item.color" class="item-color-tag">{{ entry.item.color }}</span>
              </div>
              <div class="item-sub">
                <span v-if="entry.item.brand" class="item-brand">{{ entry.item.brand }}</span>
                <template v-if="entry.item.category">
                  <span class="item-sub-sep" v-if="entry.item.brand"> · </span>
                  <span>{{ formatCategory(entry.item.category) }}</span>
                </template>
                <template v-if="entry.item.sale_price">
                  <span class="item-sub-sep"> · </span>
                  <span class="item-price">{{ currencySymbol(entry.item.sale_currency || entry.item.currency) }} {{ Number(entry.item.sale_price).toLocaleString(numberLocale(), { minimumFractionDigits: 2 }) }}</span>
                </template>
              </div>
              <div v-if="entry.item.barcode" class="item-barcode-row">
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="10" height="10" style="flex-shrink:0"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9V5a2 2 0 012-2h2M3 15v4a2 2 0 002 2h2m10-18h2a2 2 0 012 2v4m0 10v4a2 2 0 01-2 2h-2M9 3h6M9 21h6" /></svg>
                <span class="item-barcode">{{ entry.item.barcode }}</span>
              </div>
              <div class="item-bottom-row">
                <div class="item-left-info">
                  <span class="stock-number" :class="'stock-' + stockAlertLevel(entry.item)">
                    {{ tr('Loja:') }}{{ displayStock(entry.item.stock_loja) }} {{ tr('· Dep.:') }}{{ displayStock(entry.item.stock_deposito) }}
                  </span>
                  <span v-if="entry.item.size" class="item-size-inline">{{ entry.item.size }}</span>
                  <span v-if="entry.item.location" class="item-location-inline">· {{ entry.item.location }}</span>
                  <span v-if="stockAlertLevel(entry.item) !== 'ok'" class="alert-badge" :class="'badge-' + stockAlertLevel(entry.item)">{{ alertLabel(stockAlertLevel(entry.item)) }}</span>
                </div>
                <div class="item-actions">
                  <button @click.stop="openMovement(entry.item)" :disabled="!hasKnownStock(entry.item)" class="action-btn move-btn erp-button erp-button--secondary erp-button--sm">{{ tr('Movimentar') }}</button>
                  <button @click.stop="openEdit(entry.item)" class="action-btn edit-btn erp-button erp-button--secondary erp-button--sm">{{ tr('Editar') }}</button>
                </div>
              </div>
            </div>
          </div><!-- /item-row-main -->

          <!-- Expanded detail section -->
          <div v-if="expandedCardIds.includes(entry.item.id)" class="item-extra" @click.stop>
            <div class="item-extra-row">
              <span class="item-extra-label">SKU</span>
              <span class="item-extra-val mono">{{ entry.item.sku_internal }}</span>
            </div>
            <div v-if="entry.item.min_stock || entry.item.max_stock" class="item-extra-row">
              <span class="item-extra-label">{{ tr('Limites') }}</span>
              <span class="item-extra-val">{{ tr('mín') }} {{ entry.item.min_stock }} {{ tr('· máx') }} {{ entry.item.max_stock }}</span>
            </div>
            <div v-if="Number(entry.item.cost_price) > 0" class="item-extra-row">
              <span class="item-extra-label">{{ tr('Custo') }}</span>
              <span class="item-extra-val">{{ currencySymbol(entry.item.cost_currency || entry.item.currency) }} {{ Number(entry.item.cost_price).toLocaleString(numberLocale(), { minimumFractionDigits: 2 }) }}</span>
            </div>
            <div v-if="entry.item.description" class="item-extra-row">
              <span class="item-extra-label">{{ tr('Descrição') }}</span>
              <span class="item-extra-val item-extra-desc">{{ entry.item.description }}</span>
            </div>
          </div>
        </div>

      </template>
    </div>

    <!-- Sentinel para infinite scroll -->
    <div ref="scrollSentinel" class="scroll-sentinel">
      <div v-if="inventoryStore.loading && inventoryStore.items.length > 0" class="loading-more">
        <div class="spinner-sm"></div>
      </div>
    </div>

    <!-- Image modal -->
    <div v-if="imageModalSrc" class="image-modal-overlay" @click="imageModalSrc = null">
      <img :src="imageModalSrc" alt="" class="image-modal-img" @click.stop />
      <button class="image-modal-close erp-button erp-button--ghost erp-button--icon" @click="imageModalSrc = null">✕</button>
    </div>

    <!-- Toast -->
    <div v-if="toast" class="toast" :class="'toast-' + toast.type">{{ tr(toast.message, toast.params) }}</div>

    <!-- Modals -->
    <BarcodeScanner v-if="showScanner" @barcode-detected="onBarcodeDetected" @close="showScanner = false" />

    <DeletedProductsModal v-if="showDeletedHistory" @close="showDeletedHistory = false" />
    <ItemFormModal
      v-if="showItemForm"
      :item="editingItem"
      :suppliers="suppliers"
      :existing-group-keys="existingGroupKeys"
      :existing-brands="existingBrands"
      :can-delete-permanently="auth.isOwner"
      :can-create-variants="['ADMIN', 'GERENTE'].includes(auth.userRole)"
      @variants-created="onVariantsCreated"
      @deleted="onItemDeleted"
      @saved="onItemSaved"
      @partial="onItemPartiallySaved"
      @close="showItemForm = false"
    />

    <MovementModal
      v-if="showMovementModal"
      :item="movementItem"
      @saved="onMovementSaved"
      @close="showMovementModal = false"
    />

    <ImportModal
      v-if="showImport"
      @imported="() => { diagnosticsRevision++; reloadItems(); inventoryStore.loadAlerts() }"
      @close="showImport = false"
    />

    <BulkEditModal
      v-if="showBulkEdit"
      :items="selectedItemsForBulkEdit"
      :distinct-brands="distinctBrands"
      :distinct-categories="distinctCategories"
      @close="showBulkEdit = false"
      @saved="onBulkEditSaved"
    />

    <BulkTransferModal
      v-if="showBulkTransfer"
      :items="selectedItemsForTransfer"
      @saved="onBulkTransferSaved"
      @close="showBulkTransfer = false"
    />

    <GroupingSuggestionModal
      v-if="showSuggestionModal"
      :items="suggestionModalItems"
      :suggested-name="suggestionModalName"
      :existing-group-keys="existingGroupKeys"
      @close="showSuggestionModal = false"
      @grouped="onSuggestionGrouped"
    />

    <LabelTemplatesModal
      v-if="showLabelTemplates"
      @close="showLabelTemplates = false"
    />

    <BulkDeleteModal v-if="showBulkDelete && auth.isOwner" :items="itemsForDeletion"
      @close="closeBulkDelete" @deleted="forgetDeletedItem" @settled="refreshAfterDeletion" />

    <!-- Barra flutuante de seleção -->
    <transition name="sel-bar">
      <div v-if="selectionMode && selectedIds.length > 0 && !showBulkEdit && !showBulkDelete" class="selection-bar">
        <span class="sel-count">{{ tr('Itens selecionados: {count}', { count: selectedIds.length }) }}</span>
        <div class="sel-actions">
          <button @click="showGroupModal = true" class="sel-btn sel-btn-primary erp-button erp-button--primary erp-button--sm">{{ tr('Agrupar') }}</button>
          <button @click="openBulkEdit" class="sel-btn sel-btn-primary erp-button erp-button--primary erp-button--sm">
            <span class="sel-label-full">{{ tr('Editar massivo') }}</span>
            <span class="sel-label-short">{{ tr('Editar') }}</span>
          </button>
          <button @click="openBulkTransfer" class="sel-btn sel-btn-transfer erp-button erp-button--primary erp-button--sm">
            <span class="sel-label-full">{{ tr('Transferir') }}</span>
            <span class="sel-label-short">{{ tr('Transf.') }}</span>
          </button>
          <button v-if="auth.isOwner" @click="openBulkDelete" class="sel-btn sel-btn-delete erp-button erp-button--danger erp-button--sm">{{ tr('Excluir') }}</button>
          <button @click="selectAll" class="sel-btn erp-button erp-button--secondary erp-button--sm">
            <span class="sel-label-full">{{ tr('Sel. todos') }}</span>
            <span class="sel-label-short">{{ tr('Todos') }}</span>
          </button>
          <button @click="selectedIds = []" class="sel-btn erp-button erp-button--secondary erp-button--sm">{{ tr('Limpar') }}</button>
        </div>
      </div>
    </transition>

    <!-- Modal de nome do grupo -->
    <div v-if="showGroupModal" class="gmodal-overlay erp-dialog-backdrop" @click.self="showGroupModal = false">
      <div v-erp-dialog class="gmodal erp-dialog erp-dialog--sm">
        <h3 class="gmodal-title erp-dialog__header">{{ tr('Definir nome do grupo') }}</h3>
        <div class="erp-dialog__body"><p class="gmodal-sub">
          {{ tr('Itens a agrupar: {count}. Defina um código ou nome de modelo:', { count: selectedUngrouped.length }) }}
        </p>
        <!-- Warning: some selected items are already in a group -->
        <div v-if="selectedAlreadyGrouped.length > 0" class="gmodal-warn">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="14" height="14" style="flex-shrink:0"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>
          {{ tr('Itens já agrupados que serão ignorados: {count}.', { count: selectedAlreadyGrouped.length }) }}
        </div>
        <div v-if="selectedUngrouped.length < 2" class="gmodal-error">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="14" height="14" style="flex-shrink:0"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
          {{ tr('Selecione pelo menos 2 itens sem grupo para poder agrupar.') }}
        </div>
        <select v-if="existingGroupKeys.length" v-model="selectedExistingGroup" class="gmodal-input"
          :aria-label="tr('Grade de destino')" :disabled="grouping || selectedUngrouped.length < 2">
          <option value="">{{ tr('Criar uma nova grade') }}</option>
          <option v-for="gk in existingGroupKeys" :key="gk" :value="gk">{{ groupTitle(gk) }}</option>
        </select>
        <input v-if="!selectedExistingGroup"
          v-model="groupNameInput"
          type="text"
          class="gmodal-input"
          :placeholder="tr('Ex: DKR003, FLC009 LUTT/NAPA...')"
          ref="groupNameInputRef"
          @keydown.enter="confirmGroup"
          :disabled="selectedUngrouped.length < 2"
        />
        <p v-if="!selectedExistingGroup" class="gmodal-hint">{{ tr('Sugestão baseada nos nomes:') }} <strong>{{ groupNameSuggestion }}</strong></p></div>
        <div class="gmodal-footer erp-dialog__footer">
          <button @click="showGroupModal = false" class="sel-btn erp-button erp-button--secondary erp-button--sm">{{ tr('Cancelar') }}</button>
          <button @click="confirmGroup" class="sel-btn sel-btn-primary erp-button erp-button--primary erp-button--sm"
            :disabled="(!selectedExistingGroup && !groupNameInput.trim()) || grouping || selectedUngrouped.length < 2">
            {{ grouping ? tr('Agrupando...') : tr('Agrupar {count}', { count: selectedUngrouped.length }) }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { taxonomyKey, uniqueLabels } from '@/services/inventoryTaxonomy'
import { vErpDialog } from '@/directives/erpDialog'
import ModuleHeader from '@/components/ModuleHeader.vue'
import { startInventoryDrag } from '@/services/inventoryDragSelection'
import { displayStock, hasKnownStock, stockAlertLevel, UNKNOWN_STOCK_MESSAGE } from '@/services/inventoryStock'
import { useInventoryI18n } from '@/components/inventory/i18n'
const { tr, numberLocale } = useInventoryI18n()
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { useInventoryStore } from '@/stores/inventory'
import { useAuthStore } from '@/stores/auth'
import { inventoryAPI, type InventoryItem, type GroupResponse, type SuggestionResponse } from '@/services/api'
import BarcodeScanner from '@/components/inventory/BarcodeScanner.vue'
import ItemFormModal from '@/components/inventory/ItemFormModal.vue'
import DeletedProductsModal from '@/components/inventory/DeletedProductsModal.vue'
import MovementModal from '@/components/inventory/MovementModal.vue'
import ImportModal from '@/components/inventory/ImportModal.vue'
import BulkDeleteModal from '@/components/inventory/BulkDeleteModal.vue'
import { useInventoryGradeLinks } from '@/composables/useInventoryGradeLinks'
import { inventoryGroupName } from '@/services/inventoryGroupNames'
import BulkEditModal from '@/components/inventory/BulkEditModal.vue'
import BulkTransferModal from '@/components/inventory/BulkTransferModal.vue'
import GroupingSuggestionModal from '@/components/inventory/GroupingSuggestionModal.vue'
import LabelTemplatesModal from '@/components/inventory/LabelTemplatesModal.vue'
import InventoryDiagnosticsPanel from '@/components/inventory/InventoryDiagnosticsPanel.vue'
import { diagnosticsMessages } from '@/components/inventory/diagnosticsMessages'

const { t: diagnosticsText } = useI18n({ useScope: 'local', messages: diagnosticsMessages })
const showDiagnostics = ref(false), diagnosticsRevision = ref(0)
const diagnosticsOpeningId = ref<string | null>(null)
const diagnosticsOpenError = ref<'openError' | 'inactive' | null>(null)
let diagnosticOpenGeneration = 0
watch(showDiagnostics, () => {
  diagnosticOpenGeneration++
  diagnosticsOpeningId.value = null
  diagnosticsOpenError.value = null
})

const mobileToolbarOpen = ref(false)
function toggleMobileToolbar() {
  mobileToolbarOpen.value = !mobileToolbarOpen.value
  if (!mobileToolbarOpen.value) openFilter.value = null
}

const route = useRoute()
const inventoryStore = useInventoryStore()
const auth = useAuthStore()

const searchQuery = ref('')
const activeStatus = ref((route.query.status as string) || '')
const showScanner = ref(false)
const showItemForm = ref(false)
const showDeletedHistory = ref(false)
const showMovementModal = ref(false)
const showImport = ref(false)
const showLabelTemplates = ref(false)
const editingItem = ref<InventoryItem | null>(null)
const movementItem = ref<InventoryItem | null>(null)
const suppliers = ref<Array<{ id: string; name: string }>>([])
const toast = ref<{ message: string; type: string; params?: Record<string, string | number> } | null>(null)
const distinctBrands = ref<string[]>([])
const distinctCategories = ref<string[]>([])
const filterBrand = ref('')
const filterCategory = ref('')
const openFilter = ref<string | null>(null)
const filterChipsRef = ref<HTMLElement | null>(null)
const brandSearch = ref('')
const categorySearch = ref('')
const filteredBrands = computed(() =>
  brandSearch.value.trim()
    ? distinctBrands.value.filter(b => taxonomyKey(b).includes(taxonomyKey(brandSearch.value)))
    : distinctBrands.value
)
const filteredCategories = computed(() =>
  categorySearch.value.trim()
    ? distinctCategories.value.filter(c => taxonomyKey(c).includes(taxonomyKey(categorySearch.value)))
    : distinctCategories.value
)
const expandedCardIds = ref<string[]>([])
const confirmRemoveChip = ref<string | null>(null)

const backendGroups = ref<GroupResponse[]>([])
const backendSuggestions = ref<SuggestionResponse[]>([])
let groupLoadGeneration = 0, suggestionLoadGeneration = 0
const hasGroups = computed(() => backendGroups.value.length > 0 || inventoryStore.items.some(i => i.group_key))

// All items visible in the current view — combines ungrouped store items + items from expanded groups.
// Needed so BulkEditModal can find grouped items (which are NOT in inventoryStore.items in group mode).
const allVisibleItems = computed(() => {
  const map = new Map<string, InventoryItem>()
  for (const item of inventoryStore.items) map.set(item.id, item)
  for (const g of backendGroups.value) {
    for (const item of g.items as InventoryItem[]) map.set(item.id, item)
  }
  return map
})
const imageModalSrc = ref<string | null>(null)
const viewMode = ref<'list' | 'compact' | 'grid'>(
  (localStorage.getItem('inv_view') as any) || 'compact'
)
const groupMode = ref(localStorage.getItem('inv_group_mode') === 'true')
const expandedGroups = ref<string[]>([])
const selectionMode = ref(false)
const selectedIds = ref<string[]>([])
const showGroupModal = ref(false)
const groupNameInput = ref('')
const selectedExistingGroup = ref('')
const groupNameInputRef = ref<HTMLInputElement | null>(null)
const editingGroupKey = ref<string | null>(null)
const editingGroupName = ref('')
const grouping = ref(false)
const showBulkEdit = ref(false)
const showBulkTransfer = ref(false)
const filterLocation = ref('')
const isDragSelecting = ref(false)
const showSuggestionModal = ref(false)
const suggestionModalItems = ref<InventoryItem[]>([])
const suggestionModalName = ref('')
const scrollSentinel = ref<HTMLElement | null>(null)
let scrollObserver: IntersectionObserver | null = null

function setView(mode: 'list' | 'compact' | 'grid') {
  viewMode.value = mode
  localStorage.setItem('inv_view', mode)
}

function toggleGroupMode() {
  groupMode.value = !groupMode.value
  localStorage.setItem('inv_group_mode', String(groupMode.value))
  inventoryStore.loadItems(1, false, groupMode.value)
  if (groupMode.value) loadGroupsFiltered()
}

function toggleExpand(groupKey: string) {
  const idx = expandedGroups.value.indexOf(groupKey)
  if (idx === -1) expandedGroups.value.push(groupKey)
  else expandedGroups.value.splice(idx, 1)
}

const filterUngroupedOnly = ref(false)
const hasActiveFilters = computed(() => !!searchQuery.value.trim() || filterUngroupedOnly.value ||
  Object.values(inventoryStore.filters).some(value => !!value))

function clearItemFilters() {
  searchQuery.value = ''
  activeStatus.value = ''
  filterBrand.value = ''
  filterCategory.value = ''
  filterLocation.value = ''
  filterUngroupedOnly.value = false
  brandSearch.value = ''
  categorySearch.value = ''
  openFilter.value = null
  Object.assign(inventoryStore.filters, {
    search: '', status: '', category: '', brand: '', location: '', size: '', color: '', location_stock: '',
  })
  if (searchTimer) { clearTimeout(searchTimer); searchTimer = null }
  reloadItems()
  if (groupMode.value) loadGroupsFiltered()
}

/** Reloads items always respecting the current groupMode (ungrouped_only when in group mode or when filterUngroupedOnly is active) */
function reloadItems(page = 1, append = false) {
  return inventoryStore.loadItems(page, append, groupMode.value || filterUngroupedOnly.value)
}

function toggleUngroupedFilter() {
  filterUngroupedOnly.value = !filterUngroupedOnly.value
  if (filterUngroupedOnly.value) {
    // Clear status filter so they don't stack
    activeStatus.value = ''
    inventoryStore.filters.status = ''
  }
  reloadItems()
}

async function loadGroups(params: Record<string, any> = {}) {
  const generation = ++groupLoadGeneration
  try {
    const groups = await inventoryAPI.getGroups(params)
    if (generation === groupLoadGeneration) backendGroups.value = groups
  } catch {}
}

function groupFilterParams(): Record<string, any> {
  const p: Record<string, any> = {}
  if (inventoryStore.filters.search) p.search = inventoryStore.filters.search
  if (filterBrand.value) p.brand = filterBrand.value
  if (filterCategory.value) p.category = filterCategory.value
  if (activeStatus.value) p.status = activeStatus.value
  if (filterLocation.value) p.location_stock = filterLocation.value
  return p
}

function loadGroupsFiltered() {
  return loadGroups(groupFilterParams())
}

async function loadSuggestions() {
  const generation = ++suggestionLoadGeneration
  try {
    const suggestions = await inventoryAPI.getSuggestions()
    if (generation === suggestionLoadGeneration) backendSuggestions.value = suggestions
  } catch {}
}

function toggleSelectionMode() {
  selectionMode.value = !selectionMode.value
  if (!selectionMode.value) {
    selectedIds.value = []
    showGroupModal.value = false
  } else {
    loadSuggestions()
  }
}

let stopDragSelection = () => {}
function onItemPointerDown(itemId: string, event: PointerEvent) {
  stopDragSelection()
  if (!selectionMode.value || !itemsContainer.value) return
  stopDragSelection = startInventoryDrag(event, itemsContainer.value, itemId,
    id => { if (!selectedIds.value.includes(id)) selectedIds.value.push(id) },
    active => { isDragSelecting.value = active })
}
watch(selectionMode, () => stopDragSelection())

function selectAll() {
  const all = new Set<string>()
  for (const entry of flatList.value) {
    if (entry.type === 'item') all.add(entry.item.id)
    else for (const item of entry.group.items) all.add(item.id)
  }
  selectedIds.value = [...all]
}

const selectedItemsForBulkEdit = ref<InventoryItem[]>([])
const showBulkDelete = ref(false), itemsForDeletion = ref<Array<{ id: string; name: string }>>([])
function openBulkDelete() {
  if (!auth.isOwner) return
  itemsForDeletion.value = selectedIds.value.map(id => ({ id, name: allVisibleItems.value.get(id)?.name || id }))
  if (itemsForDeletion.value.length) showBulkDelete.value = true
}
function closeBulkDelete() { showBulkDelete.value = false; refreshAfterDeletion() }
function refreshAfterDeletion() { return Promise.all([reloadItems(), loadGroupsFiltered(), inventoryStore.loadAlerts()]) }


function openBulkEdit() {
  // Capture items eagerly at click time to avoid reactivity timing issues.
  // backendGroups may reload while the modal is open, so we snapshot now.
  const map = allVisibleItems.value
  selectedItemsForBulkEdit.value = selectedIds.value
    .map(id => map.get(id))
    .filter(Boolean) as InventoryItem[]
  showBulkEdit.value = true
}

const selectedItemsForTransfer = ref<InventoryItem[]>([])

function openBulkTransfer() {
  const map = allVisibleItems.value
  selectedItemsForTransfer.value = selectedIds.value
    .map(id => map.get(id))
    .filter(Boolean) as InventoryItem[]
  showBulkTransfer.value = true
}

function setLocationFilter(loc: string) {
  // Toggle off if already active
  filterLocation.value = filterLocation.value === loc ? '' : loc
  inventoryStore.filters.location_stock = filterLocation.value
  inventoryStore.loadItems(1, false, groupMode.value)
  if (groupMode.value) loadGroupsFiltered()
}

function toggleCardExpand(id: string) {
  const idx = expandedCardIds.value.indexOf(id)
  if (idx === -1) expandedCardIds.value.push(id)
  else expandedCardIds.value.splice(idx, 1)
}

function onCardClick(itemId: string, e: MouseEvent) {
  const target = e.target as HTMLElement
  // Don't expand when clicking interactive elements or images
  if (target.closest('button, a, .item-thumb-wrap, .item-grid-image, .card-check')) return
  if (selectionMode.value) {
    if (!isDragSelecting.value) toggleSelection(itemId)
  } else {
    toggleCardExpand(itemId)
  }
}

async function doRemoveFromGroup(itemId: string, groupKey: string) {
  confirmRemoveChip.value = null
  await removeItemFromGroup(itemId, groupKey)
}

function toggleSelection(id: string) {
  const idx = selectedIds.value.indexOf(id)
  if (idx === -1) selectedIds.value.push(id)
  else selectedIds.value.splice(idx, 1)
}

// Items selected that are NOT already in a group — only these can be grouped
const selectedUngrouped = computed(() =>
  inventoryStore.items.filter(i => selectedIds.value.includes(i.id) && !i.group_key)
)
// Items selected that ARE already in a group — will be excluded from grouping
const selectedAlreadyGrouped = computed(() =>
  inventoryStore.items.filter(i => selectedIds.value.includes(i.id) && !!i.group_key)
)

const groupNameSuggestion = computed(() => {
  if (selectedIds.value.length < 2) return ''
  const selected = inventoryStore.items.filter(i => selectedIds.value.includes(i.id))
  if (!selected.length) return ''
  const names = selected.map(i => i.name)
  let prefix = names[0]
  for (const name of names.slice(1)) {
    let i = 0
    while (i < prefix.length && i < name.length && prefix[i] === name[i]) i++
    prefix = prefix.slice(0, i)
  }
  return prefix.trim().replace(/[-_\s]+$/, '')
})

watch(showGroupModal, (val) => {
  if (val) {
    selectedExistingGroup.value = ''
    groupNameInput.value = groupNameSuggestion.value
    nextTick(() => groupNameInputRef.value?.focus())
  }
})

async function confirmGroup() {
  const key = selectedExistingGroup.value || groupNameInput.value.trim()
  const name = selectedExistingGroup.value ? groupTitle(key) : key
  if (!key || grouping.value) return
  const idsToGroup = selectedUngrouped.value.map(i => i.id)
  if (idsToGroup.length < 2) return
  grouping.value = true
  try {
    await inventoryAPI.groupItems(idsToGroup, key)
    showToast('{count} itens agrupados como "{name}"', 'success', { count: idsToGroup.length, name })
    showGroupModal.value = false
    selectionMode.value = false
    selectedIds.value = []
    groupNameInput.value = ''
    groupMode.value = true
    localStorage.setItem('inv_group_mode', 'true')
    await Promise.all([reloadItems(), loadGroups()])
  } catch (e: any) {
    showToast(e.response?.data?.detail || 'Erro ao agrupar', 'error')
  } finally {
    grouping.value = false
  }
}

function currencySymbol(c: string): string {
  const map: Record<string, string> = { PYG: 'G$', BRL: 'R$', USD: 'U$', EUR: '€' }
  return map[c] || c
}

function formatCategory(cat: string): string {
  return cat ? cat.replace('>', ' › ') : ''
}

interface GroupEntry {
  _isGroup: true
  group_key: string
  items: InventoryItem[]
  total_stock: number | null
}

type FlatEntry = { type: 'group'; group: GroupEntry } | { type: 'item'; item: InventoryItem }

const flatList = computed<FlatEntry[]>(() => {
  if (!groupMode.value) {
    return inventoryStore.items.map(item => ({ type: 'item' as const, item }))
  }

  // Em modo grupo: backendGroups já vem filtrado pelo backend quando há busca
  const groupedItemIds = new Set<string>()
  const result: FlatEntry[] = []

  for (const g of backendGroups.value) {
    const visibleItems = g.items as InventoryItem[]
    for (const item of visibleItems) groupedItemIds.add(item.id)

    result.push({ type: 'group', group: {
      _isGroup: true,
      group_key: g.group_key,
      items: visibleItems,
      total_stock: g.total_stock,
    }})
    // Itens expandidos são renderizados DENTRO do card de grupo (não como vizinhos no grid)
  }

  // Itens soltos da página atual (já filtrados pelo backend via API)
  for (const item of inventoryStore.items) {
    if (!item.group_key && !groupedItemIds.has(item.id)) {
      result.push({ type: 'item', item })
    }
  }

  return result
})

const itemsContainer = ref<HTMLElement>()
const visibleGradeNumbers = computed(() => {
  const groups = new Map<string, number>()
  for (const entry of flatList.value) {
    if (entry.type === 'item' && entry.item.group_key && !groups.has(entry.item.group_key)) groups.set(entry.item.group_key, groups.size + 1)
  }
  return groups
})
const gradeConnections = useInventoryGradeLinks(itemsContainer, computed(() => [flatList.value, viewMode.value]), computed(() => !groupMode.value))

function groupAlertLevel(items: InventoryItem[]): string {
  if (items.some(item => !hasKnownStock(item))) return 'unknown'
  if (items.some(i => i.alert_level === 'out')) return 'out'
  if (items.some(i => i.alert_level === 'low')) return 'low'
  if (items.some(i => i.alert_level === 'high')) return 'high'
  return 'ok'
}

/** Returns 'deposito' if ALL stock is in depósito, 'loja' if all in loja, 'mixed' otherwise. */
function groupLocationBadge(items: InventoryItem[]): 'deposito' | 'loja' | 'mixed' | null {
  if (items.some(item => !hasKnownStock(item))) return null
  const hasStock = items.some(i => hasKnownStock(i) && i.current_stock > 0)
  if (!hasStock) return null
  if (items.every(i => i.stock_loja === 0)) return 'deposito'
  if (items.every(i => i.stock_deposito === 0)) return 'loja'
  return 'mixed'
}

const groupDisplayNames = computed(() => {
  const names = new Map<string, string>()
  for (const group of backendGroups.value) {
    names.set(group.group_key, inventoryGroupName(group.group_key, group.items, tr('Grade')))
  }
  // A filtered or not-yet-loaded group list may omit a visible card's grade.
  const members = new Map<string, InventoryItem[]>()
  for (const item of inventoryStore.items) {
    if (!item.group_key || names.has(item.group_key)) continue
    const rows = members.get(item.group_key) || []
    rows.push(item); members.set(item.group_key, rows)
  }
  for (const [key, items] of members) names.set(key, inventoryGroupName(key, items, tr('Grade')))
  return names
})
function groupTitle(key: string): string {
  return groupDisplayNames.value.get(key) || inventoryGroupName(key, [], tr('Grade'))
}
const existingGroupKeys = computed<string[]>(() =>
  backendGroups.value.map(g => g.group_key).sort((a, b) => groupTitle(a).localeCompare(groupTitle(b)))
)

const existingBrands = computed<string[]>(() => {
  const s = new Set<string>()
  for (const item of inventoryStore.items) {
    if (item.brand) s.add(item.brand)
  }
  return uniqueLabels([...distinctBrands.value, ...s])
})

// ── Size ordering ────────────────────────────────────────────────────────────
// Comprehensive clothing size order — covers international and Brazilian/Portuguese
const KNOWN_SIZE_ORDER: Record<string, number> = {
  // International
  XXS: 0, XS: 1, S: 2, M: 3, L: 4, XL: 5,
  '2XL': 6, XXL: 6, '3XL': 7, XXXL: 7,
  '4XL': 8, XXXXL: 8, '5XL': 9, XXXXXL: 9,
  // Brazilian/Portuguese
  PP: 10, P: 11, G: 12, GG: 13, XG: 14, XGG: 15, XXG: 16, XXXG: 17,
  // Universal
  U: 99, UN: 99,
}
function sizeSortKey(size?: string | null): [number, number, string] {
  if (!size) return [3, 0, '']
  const s = size.trim().toUpperCase()
  if (s in KNOWN_SIZE_ORDER) return [1, KNOWN_SIZE_ORDER[s], s]
  // Pure numeric only (shoe sizes: 36, 37, 38...) — strict regex avoids "2XL" → 2
  if (/^\d+(\.\d+)?$/.test(s)) return [0, parseFloat(s), s]
  return [2, 0, s]
}
function sortedByColorThenSize<T extends { size?: string | null; color?: string | null }>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    const ca = (a.color || '').toLowerCase()
    const cb = (b.color || '').toLowerCase()
    if (ca !== cb) return ca.localeCompare(cb)
    const [at, an, as_] = sizeSortKey(a.size)
    const [bt, bn, bs] = sizeSortKey(b.size)
    if (at !== bt) return at - bt
    if (an !== bn) return an - bn
    return as_.localeCompare(bs)
  })
}

function startEditGroupName(groupKey: string) {
  editingGroupKey.value = groupKey
  editingGroupName.value = groupTitle(groupKey)
  nextTick(() => {
    const input = document.querySelector<HTMLInputElement>('.group-name-input')
    input?.focus()
    input?.select()
  })
}

async function saveGroupName(oldKey: string) {
  if (editingGroupKey.value !== oldKey) return
  const newKey = editingGroupName.value.trim()
  editingGroupKey.value = null
  if (!newKey || newKey === groupTitle(oldKey)) return
  try {
    await inventoryAPI.renameGroup(oldKey, newKey)
    showToast('Grupo renomeado para "{name}"', 'success', { name: newKey })
    await Promise.all([reloadItems(), loadGroupsFiltered()])
  } catch (e: any) {
    showToast(e.response?.data?.detail || 'Erro ao renomear grupo', 'error')
  }
}

async function handleUngroup(groupKey: string) {
  const name = groupTitle(groupKey)
  try {
    await inventoryAPI.ungroup(groupKey)
    showToast('Grupo "{name}" desagrupado', 'success', { name })
    await Promise.all([reloadItems(), loadGroups()])
  } catch (e: any) {
    showToast(e.response?.data?.detail || 'Erro ao desagrupar', 'error')
  }
}

async function removeItemFromGroup(itemId: string, groupKey: string) {
  const name = groupTitle(groupKey)
  try {
    await inventoryAPI.removeFromGroup(itemId)
    showToast('Item removido do grupo "{name}"', 'success', { name })
    await Promise.all([reloadItems(), loadGroupsFiltered()])
  } catch (e: any) {
    showToast(e.response?.data?.detail || 'Erro ao remover do grupo', 'error')
  }
}

const statusChips = computed(() => [
  { value: '', label: 'Todos', count: inventoryStore.alerts?.total_active_items },
  { value: 'low_stock', label: 'Baixo', count: inventoryStore.alerts?.low_stock_count },
  { value: 'out_of_stock', label: 'Sem estoque', count: inventoryStore.alerts?.out_of_stock_count },
  { value: 'overstocked', label: 'Excesso', count: inventoryStore.alerts?.overstocked_count },
  { value: 'inactive', label: 'Inativos', count: inventoryStore.alerts?.inactive_count },
  { value: 'unknown_stock', label: 'Revisar estoque', count: inventoryStore.alerts?.unknown_stock_count },
])

let searchTimer: ReturnType<typeof setTimeout> | null = null
watch(searchQuery, (val) => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    const trimmed = val.trim()
    if (trimmed === inventoryStore.filters.search) return
    inventoryStore.filters.search = trimmed
    if (groupMode.value) {
      Promise.all([loadGroupsFiltered(), inventoryStore.loadItems(1, false, true)])
    } else {
      reloadItems()
    }
  }, 300)
})

function clearSearch() {
  if (searchTimer) { clearTimeout(searchTimer); searchTimer = null }
  searchQuery.value = ''
  inventoryStore.filters.search = ''
  if (groupMode.value) {
    Promise.all([loadGroupsFiltered(), inventoryStore.loadItems(1, false, true)])
  } else {
    reloadItems()
  }
}

function setStatusFilter(status: string) {
  activeStatus.value = status
  inventoryStore.filters.status = status
  filterUngroupedOnly.value = false
  inventoryStore.loadItems(1, false, groupMode.value)
  if (groupMode.value) loadGroupsFiltered()
}

function toggleFilter(key: string) {
  if (openFilter.value === key) {
    openFilter.value = null
    brandSearch.value = ''
    categorySearch.value = ''
  } else {
    openFilter.value = key
    brandSearch.value = ''
    categorySearch.value = ''
  }
}

function setFilter(key: 'brand' | 'category', value: string) {
  if (key === 'brand') filterBrand.value = value
  else filterCategory.value = value
  openFilter.value = null
  brandSearch.value = ''
  categorySearch.value = ''
  inventoryStore.filters.brand = filterBrand.value
  inventoryStore.filters.category = filterCategory.value
  inventoryStore.loadItems(1, false, groupMode.value)
  if (groupMode.value) loadGroupsFiltered()
}

// Backend-driven suggestions (works across ALL items, not just loaded page)
const suggestedGroups = computed(() => backendSuggestions.value)

function selectSuggestedGroup(sg: SuggestionResponse) {
  suggestionModalItems.value = sg.items as InventoryItem[]
  suggestionModalName.value = sg.name
  showSuggestionModal.value = true
}

async function onSuggestionGrouped(groupKey: string, count: number) {
  showSuggestionModal.value = false
  showToast('{count} itens agrupados como "{name}"', 'success', { count, name: groupKey })
  groupMode.value = true
  localStorage.setItem('inv_group_mode', 'true')
  await Promise.all([reloadItems(), loadGroups()])
}

function loadMore() {
  const nextPage = inventoryStore.pagination.page + 1
  reloadItems(nextPage, true)
}

function openCreate() {
  editingItem.value = null
  showItemForm.value = true
}

function openEdit(item: InventoryItem) {
  editingItem.value = item
  showItemForm.value = true
}

async function openDiagnosticItem(id: string) {
  const request = ++diagnosticOpenGeneration
  diagnosticsOpeningId.value = id
  diagnosticsOpenError.value = null
  try {
    const item = await inventoryAPI.getItem(id)
    if (request !== diagnosticOpenGeneration || !showDiagnostics.value || showItemForm.value) return
    if (!item.is_active) { diagnosticsOpenError.value = 'inactive'; return }
    openEdit(item)
  } catch {
    if (request === diagnosticOpenGeneration) diagnosticsOpenError.value = 'openError'
  } finally {
    if (request === diagnosticOpenGeneration) diagnosticsOpeningId.value = null
  }
}

function openMovement(item: InventoryItem) {
  if (!hasKnownStock(item)) { showToast(UNKNOWN_STOCK_MESSAGE, 'warning'); return }
  movementItem.value = item
  showMovementModal.value = true
}

function onBarcodeDetected(code: string) {
  showScanner.value = false
  searchQuery.value = code
}

function forgetDeletedItem(id: string) {
  selectedIds.value = selectedIds.value.filter(value => value !== id)
  inventoryStore.forgetDeletedItem(id)
  groupLoadGeneration++; suggestionLoadGeneration++
  backendGroups.value = backendGroups.value.map(group => {
    const items = group.items.filter(item => item.id !== id)
    return { ...group, items, total_stock: items.some(item => item.current_stock == null) ? null : items.reduce((sum, item) => sum + item.current_stock!, 0) }
  }).filter(group => group.items.length)
  backendSuggestions.value = backendSuggestions.value.map(group => ({ ...group, items: group.items.filter(item => item.id !== id) })).filter(group => group.items.length > 1)
  diagnosticsRevision.value++
}

async function onItemDeleted(id: string) {
  showItemForm.value = false
  editingItem.value = null
  forgetDeletedItem(id)
  showToast('Produto excluído definitivamente.', 'success')
  await refreshAfterDeletion()
}

async function onVariantsCreated(result: { created: unknown[] }) {
  diagnosticsRevision.value++
  showItemForm.value = false
  showToast('Novos tamanhos: {count}', 'success', { count: result.created.length })
  await Promise.all([reloadItems(), loadGroupsFiltered(), inventoryStore.loadAlerts()])
}

function onItemSaved(item: InventoryItem) {
  diagnosticsRevision.value++
  showItemForm.value = false
  showToast('Item "{name}" salvo com sucesso', 'success', { name: item.name })
  reloadItems()
}

function onItemPartiallySaved() {
  diagnosticsRevision.value++
  // The form remains open with the exact completed steps and prevents a duplicate retry.
  reloadItems()
  inventoryStore.loadAlerts()
  if (groupMode.value) loadGroupsFiltered()
}

function onMovementSaved() {
  diagnosticsRevision.value++
  showMovementModal.value = false
  showToast('Movimentação registrada', 'success')
  reloadItems()
}

async function onBulkEditSaved() {
  diagnosticsRevision.value++
  showBulkEdit.value = false
  selectionMode.value = false
  selectedIds.value = []
  showToast('Itens atualizados com sucesso', 'success')
  await Promise.all([reloadItems(), loadGroupsFiltered()])
}

async function onBulkTransferSaved() {
  diagnosticsRevision.value++
  showBulkTransfer.value = false
  selectionMode.value = false
  selectedIds.value = []
  showToast('Transferência realizada com sucesso', 'success')
  reloadItems()
}

function alertLabel(level: string | undefined) {
  const labels: Record<string, string> = {
    out: 'Sem estoque', low: 'Baixo', high: 'Excesso', ok: 'OK', inactive: 'Inativo', unknown: 'Revisar estoque'
  }
  return tr(labels[level || 'ok'] || 'OK')
}

function showToast(message: string, type: string, params?: Record<string, string | number>) {
  toast.value = { message, type, params }
  setTimeout(() => { toast.value = null }, 3000)
}

function onDocClick(e: MouseEvent) {
  if (filterChipsRef.value && !filterChipsRef.value.contains(e.target as Node)) {
    openFilter.value = null
    brandSearch.value = ''
    categorySearch.value = ''
  }
  const target = e.target as HTMLElement
  if (!target.closest('.chip-remove-wrap')) {
    confirmRemoveChip.value = null
  }
}

onUnmounted(() => {
  stopDragSelection()
  diagnosticOpenGeneration++
  if (searchTimer) clearTimeout(searchTimer)
  scrollObserver?.disconnect()
  document.removeEventListener('click', onDocClick)
})

async function autoLoadRemainingPages() {
  const { total_pages } = inventoryStore.pagination
  const isGrouped = groupMode.value
  for (let p = 2; p <= total_pages; p++) {
    if (inventoryStore.filters.search || inventoryStore.filters.status) return
    await inventoryStore.loadItems(p, true, isGrouped)
  }
}

onMounted(async () => {
  if (route.query.status) {
    inventoryStore.filters.status = route.query.status as string
    activeStatus.value = route.query.status as string
  }
  await Promise.all([
    inventoryStore.loadItems(1, false, groupMode.value),
    inventoryStore.loadAlerts(),
    loadGroups(),
  ])
  if (route.query.new === '1') {
    showItemForm.value = true
  }
  // Load remaining pages in background so full catalog is available immediately
  autoLoadRemainingPages()
  try {
    const supplierList = await inventoryAPI.getSuppliers()
    suppliers.value = supplierList
  } catch {}
  try {
    const dv = await inventoryAPI.getDistinctValues()
    distinctBrands.value = uniqueLabels(dv.brands)
    distinctCategories.value = uniqueLabels(dv.categories)
  } catch {}

  document.addEventListener('click', onDocClick)

  nextTick(() => {
    if (scrollSentinel.value) {
      scrollObserver = new IntersectionObserver(([entry]) => {
        if (
          entry.isIntersecting &&
          !inventoryStore.loading &&
          inventoryStore.pagination.page < inventoryStore.pagination.total_pages
        ) {
          loadMore()
        }
      }, { rootMargin: '300px' })
      scrollObserver.observe(scrollSentinel.value)
    }
  })
})
</script>

<style scoped>
.stock-unknown { color: #92400e; }
.badge-unknown, .chip-alert-unknown { background: #fffbeb; color: #92400e; border-color: #f59e0b; }
.alert-unknown, .exp-alert-unknown { border-left-color: #f59e0b; }
.action-btn:disabled, .exp-btn:disabled { opacity: .4; cursor: not-allowed; }
.inventory-view { min-height: 100vh; background: #f9fafb; }
.list-load-error { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: .75rem; margin: 1rem; padding: 1rem; border: 1px solid #fecaca; border-radius: 10px; background: #fef2f2; color: #991b1b; font-size: .85rem; }
.list-load-error p { margin: .35rem 0 0; font-size: .8rem; }
.list-load-error .btn:disabled { opacity: .5; cursor: not-allowed; }
.mobile-toolbar-bar { display:none; }
.sticky-toolbar { position: sticky; top: 0; z-index: 30; background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.btn { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.875rem; cursor: pointer; border: none; font-weight: 500; }
.btn-primary { background: #3b82f6; color: white; }
.btn-secondary { background: white; color: #374151; border: 1px solid #d1d5db; }
@media (max-width: 600px) {
  .mobile-toolbar-bar { display:flex; align-items:center; gap:.5rem; min-height:52px; padding:.35rem .75rem; box-sizing:border-box; }
  .mobile-toolbar-title { display:flex; flex-direction:column; flex:1; min-width:0; color:#111827; font-size:.95rem; }
  .mobile-toolbar-title span { color:#2563eb; font-size:.65rem; line-height:1.2; }
  .mobile-toolbar-toggle { flex-shrink:0; min-height:36px; }
  .mobile-toolbar-toggle svg { transition:transform .15s; }
  .mobile-toolbar-toggle svg.expanded { transform:rotate(180deg); }
  .inventory-toolbar-panel.mobile-collapsed { display:none; }
  .inventory-toolbar-panel { max-height:calc(100dvh - 112px); overflow-y:auto; overscroll-behavior:contain; }
  .inventory-toolbar-panel :deep(.erp-module-header__heading) { display:none; }
  .inventory-toolbar-panel :deep(.erp-module-header) { padding:.5rem .75rem; margin:0; }
  .inventory-toolbar-panel :deep(.erp-module-header__actions) { width:100%; justify-content:flex-start; }
  .inventory-toolbar-panel .chip-dropdown { position:static; width:min(260px, calc(100vw - 3rem)); max-height:220px; margin-top:.35rem; }
  .btn { padding: 0.35rem 0.65rem; font-size: 0.75rem; gap: 0.25rem; }
  .btn svg { width: 13px !important; height: 13px !important; }
  .btn-modelos-ia-desktop { display: none; }
}
.search-section { padding: 0.6rem 1rem 0.75rem; position: relative; border-bottom: 1px solid #f3f4f6; }
.search-row { display: flex; gap: 0.75rem; margin-bottom: 0.75rem; }
.search-box { flex: 1; position: relative; }
.search-icon { position: absolute; left: 0.75rem; top: 50%; transform: translateY(-50%); width: 1rem; height: 1rem; color: #9ca3af; }
.search-input { width: 100%; padding: 0.625rem 0.75rem 0.625rem 2.25rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; outline: none; box-sizing: border-box; }
.search-input:focus { border-color: #3b82f6; }
.search-input-clearable { padding-right: 2rem; }
.search-clear-btn { position: absolute; right: 0.55rem; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; color: #9ca3af; padding: 0.2rem; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
.search-clear-btn:hover { color: #374151; background: #f3f4f6; }
.camera-btn { padding: 0.625rem; background: white; border: 1px solid #d1d5db; border-radius: 8px; cursor: pointer; color: #374151; }
.chip { padding: 0.375rem 0.75rem; border-radius: 20px; background: #f3f4f6; border: 1px solid #e5e7eb; font-size: 0.8rem; cursor: pointer; color: #374151; display: flex; align-items: center; gap: 0.25rem; }
.chip.active { background: #dbeafe; border-color: #3b82f6; color: #1d4ed8; }
.chip-loc { }
.chip-loc.active { background: #dbeafe; border-color: #3b82f6; color: #1d4ed8; }
.chip-inactive.active { background: #fee2e2; border-color: #ef4444; color: #dc2626; }
.chip-inactive.active .chip-count { background: #dc2626; color: white; }
.chip-count { background: #bfdbfe; color: #1e40af; border-radius: 10px; padding: 0 5px; font-size: 0.7rem; min-width: 16px; text-align: center; }
.chip.active .chip-count { background: #2563eb; color: white; }
.loading-state { display: flex; flex-direction: column; align-items: center; padding: 3rem; color: #6b7280; gap: 1rem; }
.spinner { width: 32px; height: 32px; border: 3px solid #e5e7eb; border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.empty-state { display: flex; flex-direction: column; align-items: center; padding: 3rem 1rem; color: #6b7280; gap: 0.5rem; }
/* ── View container ──────────────────────────────────────────────────────────── */
.items-container {
  position: relative;
  padding: 0 1rem 1rem;
}

/* --- COMPACT view (default, 2 cols) --- */
.view-compact {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.3rem;
}
.view-compact .item-grid-image { display: none; }

/* --- LIST view (1 col, linha única por item) --- */
.view-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.view-list .item-card { padding: 0.18rem 0.65rem; border-radius: 5px; }
.view-list .item-grid-image { display: none; }
.view-list .item-thumb-wrap { display: none; }

/* ── List single-line row ──────────────────────────────────────────────────── */
.item-list-row { display: flex; align-items: center; width: 100%; min-width: 0; gap: 0; min-height: 32px; }
.list-left { display: flex; align-items: center; flex: 1; min-width: 0; overflow: hidden; }
.list-name { font-weight: 600; font-size: 0.8rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex-shrink: 1; min-width: 40px; }
.list-sep { color: #d1d5db; margin: 0 0.18rem; font-size: 0.72rem; flex-shrink: 0; }
.list-sep-subtle { opacity: 0.5; }
.list-sep-spaced { margin: 0 0.3rem; }
.list-attr { font-size: 0.72rem; color: #6b7280; white-space: nowrap; flex-shrink: 0; }
.list-brand-tag { font-size: 0.72rem; font-weight: 600; color: #374151; white-space: nowrap; flex-shrink: 0; }
.list-size-badge { font-size: 0.62rem; font-weight: 700; color: #374151; background: #f3f4f6; border-radius: 3px; padding: 0.05rem 0.28rem; white-space: nowrap; flex-shrink: 0; }
.list-cat-tag { flex-shrink: 1; overflow: hidden; text-overflow: ellipsis; min-width: 20px; }
.list-stock { font-size: 0.72rem; font-weight: 700; white-space: nowrap; flex-shrink: 0; }
.list-price { font-size: 0.72rem; color: #059669; font-weight: 600; white-space: nowrap; flex-shrink: 0; }
.list-barcode { font-family: monospace; font-size: 0.66rem; color: #111827; white-space: nowrap; flex-shrink: 0; }
.list-actions { display: flex; gap: 0.35rem; margin-left: 0.75rem; flex-shrink: 0; }
.list-btn { padding: 0.25rem 0.65rem !important; font-size: 0.72rem !important; }

/* --- GRID view (imagem em destaque, infos em linhas) --- */
.view-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 0.5rem;
}
.view-grid .item-card { padding: 0; overflow: hidden; }
.view-grid .item-grid-image {
  display: flex;
  width: 100%;
  height: 110px;
  overflow: hidden;
  background: #f3f4f6;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.view-grid .item-grid-img { width: 100%; height: 100%; object-fit: cover; }
.view-grid .item-grid-placeholder { color: #d1d5db; }
.view-grid .item-thumb-wrap { display: none; }
.view-grid .item-row-main { padding: 0.5rem 0.6rem; }
.view-grid .item-info { gap: 0.25rem; }
.view-grid .item-name { font-size: 0.78rem; white-space: normal; line-height: 1.3; }
.view-grid .item-name-row { flex-direction: column; align-items: flex-start; gap: 0.2rem; }
.view-grid .item-color-tag { max-width: none; }
.view-grid .item-sub { flex-wrap: wrap; }
.view-grid .item-bottom-row { flex-direction: column; align-items: flex-start; gap: 0.35rem; margin-top: 0.25rem; }
.view-grid .item-actions { width: 100%; gap: 0.25rem; }
/* Keep both labels on one row even in the narrowest square cards. */
:is(#app, body) .view-grid .item-actions > .action-btn {
  flex: 1 1 auto;
  min-width: 0;
  padding: 0.25rem;
  font-size: 0.6875rem;
  white-space: nowrap;
}

@media (max-width: 600px) {
  .view-compact { grid-template-columns: minmax(0, 1fr); }
  .view-grid { grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }
  .item-color-tag { max-width: 60px; overflow: hidden; text-overflow: ellipsis; }
}

/* ── Item grid image (hidden by default, shown in grid view) ─── */
.item-grid-image { display: none; }
.item-grid-img { width: 100%; height: 100%; object-fit: cover; display: block; }
.item-grid-placeholder { color: #d1d5db; display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; }
.item-grid-image.thumb-clickable { cursor: zoom-in; }

/* ── Infinite scroll sentinel ──────────────────────────────────── */
.scroll-sentinel { height: 40px; display: flex; align-items: center; justify-content: center; }
.loading-more { display: flex; align-items: center; justify-content: center; padding: 0.5rem; }
.spinner-sm { width: 20px; height: 20px; border: 2px solid #e5e7eb; border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.8s linear infinite; }

/* ── Filter chips ─────────────────────────────────────────────── */
.filter-chips { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.5rem; }

/* ── Chip dropdown filters ────────────────────────────────────── */
.chip-dd-wrap { position: relative; }
.chip-caret { font-size: 0.6rem; margin-left: 0.2rem; }
.chip-dropdown {
  position: absolute; top: calc(100% + 4px); left: 0; z-index: 200;
  background: white; border: 1px solid #e5e7eb; border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.1); min-width: 160px; overflow: hidden;
  max-height: 240px; overflow-y: auto;
}
.chip-dd-search-wrap { padding: 0.35rem 0.5rem; border-bottom: 1px solid #f3f4f6; position: sticky; top: 0; background: white; z-index: 1; }
.chip-dd-search { width: 100%; font-size: 0.78rem; border: 1px solid #e5e7eb; border-radius: 5px; padding: 0.25rem 0.5rem; outline: none; box-sizing: border-box; color: #374151; }
.chip-dd-search:focus { border-color: #93c5fd; }
.chip-dd-opt {
  display: block; width: 100%; text-align: left;
  padding: 0.45rem 0.85rem; font-size: 0.82rem; color: #374151;
  background: none; border: none; cursor: pointer;
}
.chip-dd-opt:hover { background: #f9fafb; }
.chip-dd-opt.active { background: #dbeafe; color: #1d4ed8; font-weight: 600; }

/* ── Suggestions bar ──────────────────────────────────────────── */
.suggestions-bar { display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; margin-top: 0.4rem; padding: 0.4rem 0.6rem; background: #fffbeb; border: 1px solid #fcd34d; border-radius: 6px; }
.sug-label { font-size: 0.72rem; color: #92400e; font-weight: 600; white-space: nowrap; }
.sug-chip { font-size: 0.72rem; padding: 0.2rem 0.55rem; border-radius: 20px; border: 1px solid #fbbf24; background: #fef3c7; color: #92400e; cursor: pointer; white-space: nowrap; }
.sug-chip:hover { background: #fde68a; }

/* ── Group card ───────────────────────────────────────────────── */
.group-card {
  background: white;
  border-radius: 7px;
  border: 1px solid #e5e7eb;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  grid-column: 1 / -1; /* sempre largura total — nunca invadem colunas */
  transition: box-shadow 0.15s;
  user-select: none;
}
.group-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.07); }
.group-card.alert-out  { border-left: 3px solid #ef4444; }
.group-card.alert-low  { border-left: 3px solid #f59e0b; }
.group-card.alert-high { border-left: 3px solid #8b5cf6; }
.group-card.alert-ok   { border-left: 3px solid #10b981; }

/* Lista: card compacto como linha de lista */
.view-list .group-card {
  border-radius: 5px;
  padding: 0.35rem 0.65rem;
  border-left-width: 3px;
}
.view-list .group-thumb-wrap { width: 26px; height: 26px; }
.view-list .group-header { margin-bottom: 0.25rem; }

/* Grade (grid): fundo levemente diferente para distinguir das tiles de item */
.view-grid .group-card {
  background: #f8fafc;
  border-style: solid;
  border-color: #e2e8f0;
}

/* Chevron animado do botão expandir */
.expand-chevron { transition: transform 0.2s ease; display: block; }
.chevron-open { transform: rotate(180deg); }
.expand-btn { display: flex; align-items: center; justify-content: center; padding: 0.25rem 0.4rem !important; }
.ungroup-btn { display: flex; align-items: center; justify-content: center; padding: 0.25rem 0.4rem !important; }

/* ── Itens expandidos dentro do card ─────────────────────────────── */
.group-exp-section {
  margin-top: 0.5rem;
  border-top: 1px solid #f0f0f0;
  padding-top: 0.35rem;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}
.group-exp-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.28rem 0.5rem;
  border-radius: 5px;
  border-left: 2px solid transparent;
  background: #fafafa;
  transition: background 0.12s;
}
.group-exp-row:hover { background: #f3f4f6; }
.exp-alert-out  { border-left-color: #ef4444; }
.exp-alert-low  { border-left-color: #f59e0b; }
.exp-alert-high { border-left-color: #8b5cf6; }
.exp-alert-ok   { border-left-color: #d1d5db; }
.exp-left { display: flex; align-items: center; gap: 0.35rem; flex: 1; min-width: 0; }
.exp-size { font-size: 0.75rem; font-weight: 700; color: #111827; white-space: nowrap; }
.exp-color { font-size: 0.7rem; color: #6b7280; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.exp-stock-info { display: flex; align-items: center; gap: 0.2rem; flex-shrink: 0; }
.exp-stock-val { font-size: 0.7rem; font-weight: 600; color: #374151; }
.exp-stock-sep { font-size: 0.65rem; color: #d1d5db; }
.exp-price { font-size: 0.7rem; font-weight: 600; color: #059669; white-space: nowrap; flex-shrink: 0; }
.exp-actions { display: flex; gap: 0.2rem; flex-shrink: 0; }
.exp-btn {
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  font-size: 0.7rem;
  font-weight: 600;
  line-height: 1.4;
  transition: opacity 0.12s;
}
.exp-btn:hover { opacity: 0.8; }
.exp-move { background: #e0f2fe; color: #0369a1; }
.exp-edit { background: #eff6ff; color: #2563eb; }

.group-header { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.4rem; flex-wrap: wrap; }
.group-thumb-wrap { flex-shrink: 0; width: 36px; height: 36px; border-radius: 5px; overflow: hidden; background: #f3f4f6; display: flex; align-items: center; justify-content: center; border: 1px solid #e5e7eb; }
.group-thumb { width: 100%; height: 100%; object-fit: cover; }
.group-thumb-placeholder { color: #9ca3af; display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; }
.thumb-clickable { cursor: zoom-in; }
.group-title-area { display: flex; align-items: center; gap: 0.5rem; min-width: 0; flex: 1; flex-wrap: wrap; }
.group-name { font-weight: 700; font-size: 0.85rem; color: #111827; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.group-name-editable { cursor: pointer; display: inline-flex; align-items: center; gap: 0.2rem; border-radius: 4px; padding: 0.05rem 0.25rem; transition: background 0.15s; }
.group-name-editable:hover { background: #eff6ff; color: #2563eb; }
.edit-pencil { opacity: 0; flex-shrink: 0; transition: opacity 0.15s; }
.group-name-editable:hover .edit-pencil { opacity: 1; }
.group-name-input { font-weight: 700; font-size: 0.85rem; color: #111827; border: 1.5px solid #3b82f6; border-radius: 5px; padding: 0.05rem 0.35rem; outline: none; background: #eff6ff; min-width: 80px; max-width: 200px; }
.group-total-stock { font-size: 0.72rem; color: #6b7280; white-space: nowrap; }
.group-loc-badge { font-size: 0.65rem; font-weight: 600; padding: 0.1rem 0.4rem; border-radius: 10px; white-space: nowrap; }
.badge-deposito { background: #ede9fe; color: #7c3aed; }
.badge-mixed { background: #e0f2fe; color: #0369a1; }
.group-barcode { font-family: monospace; font-size: 0.68rem; color: #9ca3af; display: flex; align-items: center; gap: 0.2rem; white-space: nowrap; }
.group-btns { display: flex; gap: 0.3rem; flex-shrink: 0; }
.size-chips { display: flex; flex-wrap: wrap; gap: 0.3rem; }
.size-chip { display: inline-flex; align-items: center; gap: 0.2rem; font-size: 0.68rem; font-weight: 600; padding: 0.18rem 0.35rem 0.18rem 0.55rem; border-radius: 20px; border: 1px solid transparent; white-space: nowrap; }
.chip-label { cursor: pointer; }
.chip-remove { background: none; border: none; cursor: pointer; font-size: 0.75rem; line-height: 1; padding: 0 0.1rem; opacity: 0.45; font-weight: 700; }
.chip-remove:hover { opacity: 1; }
.chip-alert-out      { background: #fee2e2; color: #dc2626; border-color: #fca5a5; }
.chip-alert-low      { background: #fef3c7; color: #d97706; border-color: #fcd34d; }
.chip-alert-high     { background: #ede9fe; color: #7c3aed; border-color: #c4b5fd; }
.chip-alert-ok       { background: #d1fae5; color: #059669; border-color: #6ee7b7; }
.chip-alert-inactive { background: #f3f4f6; color: #9ca3af; border-color: #e5e7eb; }
.expand-btn  { background: #f0f9ff; color: #0369a1; }
.ungroup-btn { background: #fff7ed; color: #c2410c; }
.sub-item { margin-left: 0.5rem; border-left: 2px solid #e5e7eb; }

/* ── Brand ─────────────────────────────────────────────────────── */
.item-brand { font-weight: 600; color: #374151; }

/* ── View switcher ────────────────────────────────────────────── */
.view-switcher { display: flex; align-items: center; gap: 0.35rem; flex-wrap: wrap; }
.view-label { font-size: 0.75rem; color: #9ca3af; margin-right: 0.1rem; }
.view-btn { display: flex; align-items: center; gap: 0.3rem; padding: 0.3rem 0.6rem; border: 1px solid #d1d5db; border-radius: 6px; background: white; color: #6b7280; cursor: pointer; font-size: 0.75rem; transition: all 0.15s; white-space: nowrap; }
.view-btn:hover { border-color: #9ca3af; color: #374151; }
.view-btn.active { background: #dbeafe; border-color: #3b82f6; color: #1d4ed8; }
.view-sep { color: #d1d5db; padding: 0 0.1rem; }
@media (max-width: 600px) {
  .view-label { display: none; }
  .view-sep { display: none; }
  .view-switcher { gap: 0.25rem; }
  .view-btn { padding: 0.3rem 0.5rem; }
}

.item-card {
  min-width: 0;
  background: white;
  border-radius: 7px;
  padding: 0.45rem 0.6rem;
  border: 1px solid #e5e7eb;
}
.item-card.alert-out    { border-left: 3px solid #ef4444; }
.item-card.alert-low    { border-left: 3px solid #f59e0b; }
.item-card.alert-high   { border-left: 3px solid #8b5cf6; }
.item-card.alert-ok     { border-left: 3px solid #10b981; }
.item-card.alert-inactive { border-left: 3px solid #9ca3af; opacity: 0.7; }

/* Main row: thumb + info side by side */
.item-row-main { display: flex; align-items: center; gap: 0.5rem; }

/* Thumbnail */
.item-thumb-wrap {
  flex-shrink: 0;
  width: 38px;
  height: 38px;
  border-radius: 5px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  display: flex;
  align-items: center;
  justify-content: center;
}
.item-thumb-wrap.thumb-clickable { cursor: zoom-in; }
.item-thumb-wrap.thumb-clickable:hover { border-color: #3b82f6; }
.item-thumb { width: 100%; height: 100%; object-fit: cover; display: block; }
.item-thumb-placeholder { color: #d1d5db; }

/* Info column */
.item-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.15rem; }

/* Row 1: Name + Color */
.item-name-row { display: flex; align-items: center; justify-content: space-between; gap: 0.4rem; min-width: 0; }
.item-name { font-weight: 600; font-size: 0.82rem; color: #111827; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.item-color-tag { font-size: 0.65rem; font-weight: 500; color: #6b7280; background: #f3f4f6; border-radius: 3px; padding: 0.1rem 0.35rem; white-space: nowrap; flex-shrink: 0; }

/* Row 2: barcode · category · price */
.item-sub { font-size: 0.68rem; color: #9ca3af; display: flex; align-items: center; flex-wrap: wrap; gap: 0; line-height: 1.3; }
.item-barcode-row { display: flex; align-items: center; gap: 0.25rem; margin-top: 0.1rem; }
.item-barcode { font-family: monospace; letter-spacing: 0.03em; font-size: 0.67rem; color: #9ca3af; }
.item-sub-sep { margin: 0 0.15rem; color: #d1d5db; }
.item-price { color: #059669; font-weight: 600; }

/* Row 3: stock + location + badge + actions */
.item-bottom-row { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.1rem; }
.item-left-info { display: flex; align-items: center; gap: 0.3rem; flex-wrap: wrap; }
.stock-number { font-size: 0.72rem; font-weight: 700; }
.stock-out      { color: #dc2626; }
.stock-low      { color: #d97706; }
.stock-high     { color: #7c3aed; }
.stock-ok       { color: #059669; }
.stock-inactive { color: #6b7280; }
.item-size-inline { font-size: 0.65rem; font-weight: 600; color: #374151; background: #f3f4f6; border-radius: 3px; padding: 0.05rem 0.3rem; }
.item-location-inline { font-size: 0.65rem; color: #9ca3af; }

/* Alert badge */
.alert-badge { font-size: 0.6rem; font-weight: 600; padding: 0.1rem 0.35rem; border-radius: 3px; white-space: nowrap; }
.badge-out      { background: #fee2e2; color: #dc2626; }
.badge-low      { background: #fef3c7; color: #d97706; }
.badge-high     { background: #ede9fe; color: #7c3aed; }
.badge-ok       { background: #d1fae5; color: #059669; }
.badge-inactive { background: #f3f4f6; color: #6b7280; }

/* Action buttons */
.item-actions { display: flex; flex-direction: row; flex-wrap: nowrap; gap: 0.3rem; flex-shrink: 0; }
.action-btn { padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.7rem; cursor: pointer; border: none; font-weight: 600; white-space: nowrap; }
.move-btn  { background: #dbeafe; color: #1d4ed8; }
.edit-btn  { background: #f3f4f6; color: #374151; }

/* ── Image modal ─────────────────────────────────────────────────────────────── */
.image-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.82);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9000;
  cursor: zoom-out;
  padding: 1rem;
}
.image-modal-img {
  max-width: min(90vw, 600px);
  max-height: 85vh;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
  cursor: default;
}
.image-modal-close {
  position: fixed;
  top: 1rem;
  right: 1rem;
  background: rgba(255,255,255,0.15);
  border: none;
  color: white;
  font-size: 1.25rem;
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}
.image-modal-close:hover { background: rgba(255,255,255,0.3); }

/* ── Selection mode ──────────────────────────────────────────────────────────── */
.btn-warning { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
.card-selected { outline: 2px solid #3b82f6; outline-offset: -2px; }
.card-check { padding:0; border:0; background:none; cursor:pointer; position: absolute; top: 0.35rem; left: 0.35rem; z-index: 2; }
.item-card { position: relative; }
.check-box {
  width: 20px; height: 20px; border-radius: 4px; border: 2px solid #d1d5db;
  background: white; display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: all 0.15s;
}
.check-box.checked { background: #3b82f6; border-color: #3b82f6; color: white; }

/* ── Selection floating bar ─────────────────────────────────────────────────── */
.selection-bar {
  position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%);
  background: #1e293b; color: white; border-radius: 12px;
  padding: 0.65rem 1rem; display: flex; align-items: center; gap: 0.75rem;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3); z-index: 1000;
  max-width: calc(100vw - 2rem);
}
.sel-count { font-size: 0.82rem; font-weight: 600; white-space: nowrap; flex-shrink: 0; }
.sel-actions { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.sel-btn { padding: 0.38rem 0.75rem; border-radius: 6px; border: none; cursor: pointer; font-size: 0.78rem; font-weight: 600; background: rgba(255,255,255,0.15); color: white; white-space: nowrap; }
.sel-btn:hover { background: rgba(255,255,255,0.25); }
.sel-btn-primary { background: #3b82f6; }
.sel-btn-primary:hover { background: #2563eb; }
.sel-btn-transfer { background: #7c3aed; }
.sel-btn-transfer:hover { background: #6d28d9; }
.sel-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.sel-label-short { display: none; }
.sel-bar-enter-active, .sel-bar-leave-active { transition: all 0.25s ease; }
.sel-bar-enter-from, .sel-bar-leave-to { opacity: 0; transform: translateX(-50%) translateY(1rem); }
@media (max-width: 500px) {
  .selection-bar {
    left: 0.75rem; right: 0.75rem; bottom: 0.75rem;
    transform: none; max-width: none;
    flex-wrap: wrap; gap: 0.4rem;
  }
  .sel-bar-enter-from, .sel-bar-leave-to { opacity: 0; transform: translateY(1rem); }
  .sel-actions { gap: 0.35rem; }
  .sel-btn { padding: 0.35rem 0.55rem; font-size: 0.72rem; }
  .sel-label-full { display: none; }
  .sel-label-short { display: inline; }
}

/* ── Group modal ─────────────────────────────────────────────────────────────── */
.gmodal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 2000; display: flex; align-items: center; justify-content: center; padding: 1rem; }
.gmodal { background: white; border-radius: 12px; padding: 1.5rem; width: 100%; max-width: 400px; }
.gmodal-title { font-size: 1.05rem; font-weight: 700; color: #111827; margin: 0 0 0.4rem; }
.gmodal-sub { font-size: 0.82rem; color: #6b7280; margin: 0 0 1rem; }
.gmodal-input { width: 100%; padding: 0.6rem 0.75rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.95rem; outline: none; box-sizing: border-box; margin-bottom: 0.5rem; }
.gmodal-input:focus { border-color: #3b82f6; }
.gmodal-hint { font-size: 0.75rem; color: #9ca3af; margin: 0 0 1.25rem; }
.gmodal-hint strong { color: #374151; }
.gmodal-footer { display: flex; justify-content: flex-end; gap: 0.75rem; }
.gmodal-footer .sel-btn { background: #f3f4f6; color: #374151; }
.gmodal-footer .sel-btn-primary { background: #3b82f6; color: white; }

/* ── Misc ────────────────────────────────────────────────────────────────────── */
.toast { position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%); padding: 0.75rem 1.5rem; border-radius: 8px; font-size: 0.9rem; font-weight: 500; z-index: 9999; white-space: nowrap; }
.toast-success { background: #065f46; color: white; }
.toast-error   { background: #7f1d1d; color: white; }
.toast-warning { background: #78350f; color: white; }

/* ── Already-grouped badge in selection mode ─────────────────────────────────── */
.check-grouped { border-color: #9ca3af; background: #f3f4f6; }
.check-grouped.checked { background: #9ca3af; border-color: #9ca3af; }
.in-group-badge {
  font-size: 0.55rem; font-weight: 700; letter-spacing: 0.04em;
  background: #e0e7ff; color: #4338ca;
  border-radius: 3px; padding: 0.1rem 0.3rem;
  margin-top: 0.15rem; text-transform: uppercase;
  white-space: nowrap;
}
.gmodal-warn {
  display: flex; align-items: flex-start; gap: 0.4rem;
  background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px;
  padding: 0.5rem 0.75rem; font-size: 0.8rem; color: #92400e; margin-bottom: 0.5rem;
}
.gmodal-error {
  display: flex; align-items: flex-start; gap: 0.4rem;
  background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px;
  padding: 0.5rem 0.75rem; font-size: 0.8rem; color: #991b1b; margin-bottom: 0.5rem;
}

/* ── Inventory stats bar ─────────────────────────────────────────────────────── */
.inv-stats {
  display: flex; align-items: center; gap: 0.35rem;
  padding: 0.3rem 0.1rem 0.15rem;
  font-size: 0.75rem; flex-wrap: wrap;
}
.inv-stat { display: flex; align-items: baseline; gap: 0.2rem; }
.inv-stat-num { font-weight: 700; color: #374151; }
.inv-stat-label { color: #9ca3af; }
.inv-stat-sep { color: #d1d5db; }
.inv-stat-warn .inv-stat-num { color: #d97706; }
.inv-stat-warn .inv-stat-label { color: #d97706; opacity: 0.8; }
.inv-stat-danger .inv-stat-num { color: #dc2626; }
.inv-stat-danger .inv-stat-label { color: #dc2626; opacity: 0.8; }
.inv-stat-btn {
  background: none; border: none; padding: 0.1rem 0.3rem;
  border-radius: 0.3rem; cursor: pointer;
  transition: background 0.15s;
}
.inv-stat-btn:hover { background: #f3f4f6; }
.inv-stat-btn-active { background: #e5e7eb !important; }
.inv-stat-btn-active .inv-stat-num { color: #111827; }
.inv-stat-btn-active .inv-stat-label { color: #374151; opacity: 1; }
.inv-stat-warn.inv-stat-btn:hover { background: #fef3c7; }
.inv-stat-warn-active { background: #fef3c7 !important; }
.inv-stat-danger.inv-stat-btn:hover { background: #fee2e2; }
.inv-stat-danger-active { background: #fee2e2 !important; }
.chip-check { margin-left: 0.2rem; font-size: 0.7rem; }

/* ── Drag-to-select ──────────────────────────────────────────────────────────── */
.items-container.drag-selecting { user-select: none; }
.items-container.drag-selecting .item-card { cursor: crosshair; }
.items-container.drag-selecting .item-card .item-actions { pointer-events: none; opacity: 0.4; }

/* ── Card expand ─────────────────────────────────────────────────────────────── */
.item-extra {
  margin-top: 0.4rem;
  padding-top: 0.35rem;
  border-top: 1px dashed #e5e7eb;
  display: flex;
  flex-direction: column;
  gap: 0.18rem;
}
.view-list .item-extra { margin-top: 0.25rem; padding: 0.25rem 0 0.1rem; }
.item-extra-row { display: flex; align-items: baseline; gap: 0.5rem; font-size: 0.68rem; }
.item-extra-label { color: #9ca3af; min-width: 52px; flex-shrink: 0; }
.item-extra-val { color: #374151; font-weight: 500; }
.item-extra-val.mono { font-family: monospace; letter-spacing: 0.03em; }
.item-extra-desc { color: #6b7280; font-weight: 400; white-space: pre-wrap; word-break: break-word; }

/* ── Chip remove confirm popover ──────────────────────────────────────────────── */
.chip-remove-wrap { position: relative; display: inline-flex; align-items: center; }
.chip-remove-confirm {
  position: absolute;
  bottom: calc(100% + 5px);
  right: 0;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 7px;
  padding: 0.3rem 0.45rem;
  box-shadow: 0 4px 14px rgba(0,0,0,0.13);
  z-index: 100;
  display: flex;
  align-items: center;
  gap: 0.3rem;
  white-space: nowrap;
}
.chip-remove-confirm span { font-size: 0.65rem; color: #374151; }
.chip-remove-confirm button { font-size: 0.65rem; padding: 0.15rem 0.4rem; border-radius: 4px; border: none; cursor: pointer; font-weight: 600; }
.chip-remove-confirm button:first-of-type { background: #ef4444; color: white; }
.chip-remove-confirm button:first-of-type:hover { background: #dc2626; }
.chip-remove-confirm button:last-of-type { background: #f3f4f6; color: #6b7280; }
.chip-remove-confirm button:last-of-type:hover { background: #e5e7eb; }

.grade-connections { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; overflow:visible; z-index:1; }
.grade-connections path { fill:none; stroke:#818cf8; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; }
.card-grade-label { display:flex; align-items:center; gap:.25rem; font-size:.64rem; line-height:1.2; color:#4f46e5; padding:.2rem .35rem; background:#eef2ff; border-radius:4px; width:fit-content; margin-bottom:.3rem; }
.item-card:has(.card-check) .card-grade-label { margin-left:2rem; }
.view-grid .card-grade-label { margin:.35rem .5rem; }
.view-list .card-grade-label { margin-bottom:.1rem; }
.sel-btn-delete { background:#dc2626; } .sel-btn-delete:hover { background:#b91c1c; }
.items-container:has(.grade-connections) { gap:.6rem; }
</style>
