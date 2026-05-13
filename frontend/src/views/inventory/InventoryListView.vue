<template>
  <div class="inventory-view">
    <div class="sticky-toolbar">
    <header class="page-header">
      <div class="header-content">
        <div class="header-left">
          <div class="header-top">
            <button @click="$router.replace('/dashboard')" class="back-button">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <h1 class="page-title">Estoque</h1>
          </div>
          <p class="page-subtitle">Gerencie os itens do inventário</p>
        </div>
        <div class="header-right">
          <button @click="showLabelTemplates = true" class="btn btn-secondary btn-modelos-ia-desktop">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            Modelos IA
          </button>
          <button @click="showImport = true" class="btn btn-secondary">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Importar
          </button>
          <button @click="openCreate" class="btn btn-primary">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            Novo item
          </button>
        </div>
      </div>
    </header>

    <!-- Search + Camera -->
    <div class="search-section">
      <div class="search-row">
        <div class="search-box">
          <svg class="search-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input v-model="searchQuery" type="text" placeholder="Buscar por nome, SKU, código..." class="search-input" :class="{ 'search-input-clearable': searchQuery }" />
          <button v-if="searchQuery" @click="clearSearch()" class="search-clear-btn" title="Limpar busca" type="button">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="14" height="14"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <button @click="showScanner = true" class="camera-btn" title="Escanear código">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>
      </div>

      <!-- Filter chips (status + marca + categoria + ver grupos) -->
      <div class="filter-chips" ref="filterChipsRef">
        <!-- Status -->
        <button
          v-for="chip in statusChips"
          :key="chip.value"
          @click="setStatusFilter(chip.value)"
          :class="['chip', { active: activeStatus === chip.value, 'chip-inactive': chip.value === 'inactive' }]"
        >
          {{ chip.label }}
          <span v-if="chip.count !== undefined" class="chip-count">{{ chip.count }}</span>
        </button>

        <!-- Marca dropdown chip -->
        <div class="chip-dd-wrap" v-if="distinctBrands.length > 0">
          <button @click="toggleFilter('brand')" :class="['chip', { active: !!filterBrand }]">
            {{ filterBrand || 'Marca' }} <span class="chip-caret">▾</span>
          </button>
          <div v-if="openFilter === 'brand'" class="chip-dropdown">
            <div class="chip-dd-search-wrap">
              <input v-model="brandSearch" class="chip-dd-search" placeholder="Buscar marca..." @click.stop type="text" autocomplete="off" />
            </div>
            <button @click="setFilter('brand', '')" :class="['chip-dd-opt', { active: !filterBrand }]">Todas as marcas</button>
            <button v-for="b in filteredBrands" :key="b" @click="setFilter('brand', b)" :class="['chip-dd-opt', { active: filterBrand === b }]">{{ b }}</button>
          </div>
        </div>

        <!-- Categoria dropdown chip -->
        <div class="chip-dd-wrap" v-if="distinctCategories.length > 0">
          <button @click="toggleFilter('category')" :class="['chip', { active: !!filterCategory }]">
            {{ filterCategory ? formatCategory(filterCategory) : 'Categoria' }} <span class="chip-caret">▾</span>
          </button>
          <div v-if="openFilter === 'category'" class="chip-dropdown">
            <div class="chip-dd-search-wrap">
              <input v-model="categorySearch" class="chip-dd-search" placeholder="Buscar categoria..." @click.stop type="text" autocomplete="off" />
            </div>
            <button @click="setFilter('category', '')" :class="['chip-dd-opt', { active: !filterCategory }]">Todas as categorias</button>
            <button v-for="c in filteredCategories" :key="c" @click="setFilter('category', c)" :class="['chip-dd-opt', { active: filterCategory === c }]">{{ formatCategory(c) }}</button>
          </div>
        </div>

        <!-- Location chips -->
        <button @click="setLocationFilter('loja')" :class="['chip', 'chip-loc', { active: filterLocation === 'loja' }]">
          Loja
          <span v-if="inventoryStore.alerts?.loja_count !== undefined" class="chip-count">{{ inventoryStore.alerts.loja_count }}</span>
        </button>
        <button @click="setLocationFilter('deposito')" :class="['chip', 'chip-loc', { active: filterLocation === 'deposito' }]">
          Depósito
          <span v-if="inventoryStore.alerts?.deposito_count !== undefined" class="chip-count">{{ inventoryStore.alerts.deposito_count }}</span>
        </button>

        <!-- Ver grades (só aparece se existem grupos) -->
        <button v-if="hasGroups" @click="toggleGroupMode" :class="['chip', { active: groupMode }]">
          Ver grades
          <span v-if="inventoryStore.alerts?.group_count" class="chip-count">{{ inventoryStore.alerts.group_count }}</span>
          <span v-if="groupMode" class="chip-check">✓</span>
        </button>
      </div>

      <!-- Sugestões de agrupamento (visível no modo seleção) -->
      <div v-if="selectionMode && suggestedGroups.length > 0" class="suggestions-bar">
        <span class="sug-label">Similares detectados:</span>
        <button
          v-for="sg in suggestedGroups.slice(0, 4)"
          :key="sg.name"
          @click="selectSuggestedGroup(sg)"
          class="sug-chip"
          :title="`${sg.items.length} itens com nome similar`"
        >
          {{ sg.name }} ({{ sg.items.length }})
        </button>
      </div>

      <!-- Inventory summary stats -->
      <div v-if="inventoryStore.alerts" class="inv-stats">
        <span class="inv-stat">
          <span class="inv-stat-num">{{ inventoryStore.alerts.total_active_items }}</span>
          <span class="inv-stat-label">itens</span>
        </span>
        <span class="inv-stat-sep">·</span>
        <span class="inv-stat">
          <span class="inv-stat-num">{{ inventoryStore.alerts.group_count }}</span>
          <span class="inv-stat-label">grades</span>
        </span>
        <span class="inv-stat-sep">·</span>
        <button
          class="inv-stat inv-stat-btn"
          :class="{ 'inv-stat-btn-active': filterUngroupedOnly }"
          @click="toggleUngroupedFilter"
          title="Filtrar itens sem grade"
        >
          <span class="inv-stat-num">{{ inventoryStore.alerts.total_active_items - inventoryStore.alerts.grouped_items_count }}</span>
          <span class="inv-stat-label">sem grade</span>
        </button>
        <template v-if="inventoryStore.alerts.low_stock_count > 0">
          <span class="inv-stat-sep">·</span>
          <button
            class="inv-stat inv-stat-btn inv-stat-warn"
            :class="{ 'inv-stat-btn-active inv-stat-warn-active': activeStatus === 'low_stock' }"
            @click="setStatusFilter(activeStatus === 'low_stock' ? '' : 'low_stock')"
            title="Filtrar estoque baixo"
          >
            <span class="inv-stat-num">{{ inventoryStore.alerts.low_stock_count }}</span>
            <span class="inv-stat-label">baixo</span>
          </button>
        </template>
        <template v-if="inventoryStore.alerts.out_of_stock_count > 0">
          <span class="inv-stat-sep">·</span>
          <button
            class="inv-stat inv-stat-btn inv-stat-danger"
            :class="{ 'inv-stat-btn-active inv-stat-danger-active': activeStatus === 'out_of_stock' }"
            @click="setStatusFilter(activeStatus === 'out_of_stock' ? '' : 'out_of_stock')"
            title="Filtrar sem estoque"
          >
            <span class="inv-stat-num">{{ inventoryStore.alerts.out_of_stock_count }}</span>
            <span class="inv-stat-label">sem estoque</span>
          </button>
        </template>
      </div>

      <!-- View mode switcher -->
      <div class="view-switcher">
        <span class="view-label">Visualização:</span>
        <button :class="['view-btn', { active: viewMode === 'list' }]" @click="setView('list')" title="Lista">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
          </svg>
          Lista
        </button>
        <button :class="['view-btn', { active: viewMode === 'compact' }]" @click="setView('compact')" title="Compacto">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 5h7M4 12h7M4 19h7M14 5h6M14 12h6M14 19h6" />
          </svg>
          Compacto
        </button>
        <button :class="['view-btn', { active: viewMode === 'grid' }]" @click="setView('grid')" title="Grade">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
          </svg>
          Grade
        </button>
        <span class="view-sep">|</span>
        <button :class="['view-btn', { active: selectionMode }]" @click="toggleSelectionMode" title="Selecionar para agrupar">
          Agrupar
        </button>
      </div>
    </div>
    </div><!-- /sticky-toolbar -->

    <!-- Loading -->
    <div v-if="inventoryStore.loading && flatList.length === 0" class="loading-state">
      <div class="spinner"></div>
      <p>Carregando itens...</p>
    </div>

    <!-- Empty state -->
    <div v-else-if="!inventoryStore.loading && flatList.length === 0" class="empty-state">
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="48" height="48">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
      </svg>
      <p>Nenhum item encontrado</p>
      <button @click="openCreate" class="btn btn-primary" style="margin-top:1rem;">Criar primeiro item</button>
    </div>

    <!-- Items list -->
    <div v-else class="items-container" :class="[`view-${viewMode}`, { 'drag-selecting': isDragSelecting }]">
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
                :src="entry.group.items.find(i => i.image_data)!.image_data"
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
                title="Clique para renomear o grupo"
              >{{ entry.group.group_key }} <svg class="edit-pencil" fill="none" viewBox="0 0 24 24" stroke="currentColor" width="11" height="11"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg></span>
              <span class="group-total-stock">Total: {{ entry.group.total_stock }}</span>
              <span
                v-if="groupLocationBadge(entry.group.items) === 'deposito'"
                class="group-loc-badge badge-deposito"
              >Depósito</span>
              <span
                v-else-if="groupLocationBadge(entry.group.items) === 'mixed'"
                class="group-loc-badge badge-mixed"
              >Loja + Dep.</span>
              <span v-if="entry.group.items.find(i => i.barcode)" class="group-barcode">
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="9" height="9"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9V5a2 2 0 012-2h2M3 15v4a2 2 0 002 2h2m10-18h2a2 2 0 012 2v4m0 10v4a2 2 0 01-2 2h-2M9 3h6M9 21h6" /></svg>
                {{ entry.group.items.find(i => i.barcode)!.barcode }}
              </span>
            </div>
            <div class="group-btns">
              <button @click.stop="toggleExpand(entry.group.group_key)" class="action-btn expand-btn" :title="expandedGroups.includes(entry.group.group_key) ? 'Recolher' : 'Expandir'">
                <svg class="expand-chevron" :class="{ 'chevron-open': expandedGroups.includes(entry.group.group_key) }" width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7"/>
                </svg>
              </button>
              <button @click.stop="handleUngroup(entry.group.group_key)" class="action-btn ungroup-btn" title="Desagrupar">
                <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7"/></svg>
              </button>
            </div>
          </div>
          <div class="size-chips">
            <span
              v-for="v in sortedByColorThenSize(entry.group.items)"
              :key="v.id"
              class="size-chip"
              :class="'chip-alert-' + v.alert_level"
              :title="v.name + ' · ' + v.sku_internal"
            >
              <span class="chip-label" @click.stop="openEdit(v)">
                {{ v.size || v.name }}&nbsp;
                <template v-if="v.stock_deposito > 0 && v.stock_loja > 0">{{ v.stock_loja }}|{{ v.stock_deposito }}</template>
                <template v-else>{{ v.current_stock }}</template>
              </span>
              <div class="chip-remove-wrap">
                <button
                  class="chip-remove"
                  title="Remover do grupo"
                  @click.stop="confirmRemoveChip = v.id"
                >×</button>
                <div v-if="confirmRemoveChip === v.id" class="chip-remove-confirm">
                  <span>Remover?</span>
                  <button @click.stop="doRemoveFromGroup(v.id, entry.group.group_key)">Sim</button>
                  <button @click.stop="confirmRemoveChip = null">Não</button>
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
              :class="'exp-alert-' + item.alert_level"
            >
              <div class="exp-left">
                <span class="exp-size">{{ item.size || item.name }}</span>
                <span v-if="item.color" class="exp-color">{{ item.color }}</span>
              </div>
              <div class="exp-stock-info">
                <template v-if="item.stock_loja !== undefined">
                  <span class="exp-stock-val">L:{{ item.stock_loja }}</span>
                  <span class="exp-stock-sep">·</span>
                  <span class="exp-stock-val">D:{{ item.stock_deposito ?? 0 }}</span>
                </template>
                <template v-else>
                  <span class="exp-stock-val">{{ item.current_stock }}</span>
                </template>
              </div>
              <span v-if="Number(item.sale_price) > 0" class="exp-price">
                {{ currencySymbol(item.sale_currency || item.currency) }}&nbsp;{{ Number(item.sale_price).toLocaleString('pt-BR', { minimumFractionDigits: 0 }) }}
              </span>
              <div class="exp-actions">
                <div class="exit-wrap">
                  <button @click.stop="confirmExitId = item.id" class="exp-btn exp-exit" title="Consumir 1" :disabled="item.current_stock <= 0">−1</button>
                  <div v-if="confirmExitId === item.id" class="exit-confirm-popover">
                    <template v-if="exitLocations(item).loja && exitLocations(item).deposito">
                      <span class="confirm-question">Retirar de:</span>
                      <button @click.stop="handleQuickExit(item, 'loja')" class="confirm-loc confirm-loja">Loja ({{ item.stock_loja }})</button>
                      <button @click.stop="handleQuickExit(item, 'deposito')" class="confirm-loc confirm-dep">Dep. ({{ item.stock_deposito }})</button>
                    </template>
                    <template v-else-if="exitLocations(item).deposito">
                      <span class="confirm-question">Retirar do Depósito?</span>
                      <button @click.stop="handleQuickExit(item, 'deposito')" class="confirm-yes">Sim</button>
                    </template>
                    <template v-else>
                      <span class="confirm-question">Retirar da Loja?</span>
                      <button @click.stop="handleQuickExit(item, 'loja')" class="confirm-yes">Sim</button>
                    </template>
                    <button @click.stop="confirmExitId = null" class="confirm-no">×</button>
                  </div>
                </div>
                <button @click.stop="openMovement(item)" class="exp-btn exp-move" title="Movimentar">⇅</button>
                <button @click.stop="openEdit(item)" class="exp-btn exp-edit" title="Editar">✏</button>
              </div>
            </div>
          </div>
        </div>

        <!-- ── CARD INDIVIDUAL ── -->
        <div
          v-else
          class="item-card"
          :data-item-id="entry.item.id"
          :class="['alert-' + entry.item.alert_level, { 'sub-item': groupMode && entry.item.group_key, 'card-selected': selectedIds.includes(entry.item.id), 'card-expanded': expandedCardIds.includes(entry.item.id) }]"
          @click="onCardClick(entry.item.id, $event)"
          @pointerdown="onItemPointerDown(entry.item.id, $event)"
        >
          <!-- Checkbox de seleção -->
          <div v-if="selectionMode" class="card-check" @click.stop="toggleSelection(entry.item.id)">
            <span :class="['check-box', { checked: selectedIds.includes(entry.item.id), 'check-grouped': !!entry.item.group_key }]">
              <svg v-if="selectedIds.includes(entry.item.id)" fill="none" viewBox="0 0 24 24" stroke="currentColor" width="12" height="12"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/></svg>
            </span>
            <span v-if="entry.item.group_key" class="in-group-badge" :title="`Já pertence ao grupo: ${entry.item.group_key}`">grade</span>
          </div>
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
              <span class="list-name" :class="'stock-' + entry.item.alert_level">{{ entry.item.name }}</span>
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
              <span class="list-stock" :class="'stock-' + entry.item.alert_level">
                <template v-if="entry.item.stock_loja !== undefined">L:{{ entry.item.stock_loja }}&nbsp;D:{{ entry.item.stock_deposito ?? 0 }}</template>
                <template v-else>{{ entry.item.current_stock }}</template>
              </span>
              <template v-if="Number(entry.item.sale_price) > 0">
                <span class="list-sep">·</span>
                <span class="list-price">{{ currencySymbol(entry.item.sale_currency || entry.item.currency) }}&nbsp;{{ Number(entry.item.sale_price).toLocaleString('pt-BR', { minimumFractionDigits: 2 }) }}</span>
              </template>
              <template v-if="entry.item.barcode">
                <span class="list-sep list-sep-subtle">·</span>
                <span class="list-barcode">{{ entry.item.barcode }}</span>
              </template>
            </div>
            <div class="list-actions">
              <div class="exit-wrap">
                <button @click.stop="confirmExitId = entry.item.id" class="action-btn exit-btn list-btn" :disabled="entry.item.current_stock <= 0">−1</button>
                <div v-if="confirmExitId === entry.item.id" class="exit-confirm-popover">
                  <template v-if="exitLocations(entry.item).loja && exitLocations(entry.item).deposito">
                    <span class="confirm-question">Retirar de:</span>
                    <button @click.stop="handleQuickExit(entry.item, 'loja')" class="confirm-loc confirm-loja">Loja ({{ entry.item.stock_loja }})</button>
                    <button @click.stop="handleQuickExit(entry.item, 'deposito')" class="confirm-loc confirm-dep">Dep. ({{ entry.item.stock_deposito }})</button>
                  </template>
                  <template v-else-if="exitLocations(entry.item).deposito">
                    <span class="confirm-question">Retirar do Depósito?</span>
                    <button @click.stop="handleQuickExit(entry.item, 'deposito')" class="confirm-yes">Sim</button>
                  </template>
                  <template v-else>
                    <span class="confirm-question">Retirar da Loja?</span>
                    <button @click.stop="handleQuickExit(entry.item, 'loja')" class="confirm-yes">Sim</button>
                  </template>
                  <button @click.stop="confirmExitId = null" class="confirm-no">×</button>
                </div>
              </div>
              <button @click.stop="openMovement(entry.item)" class="action-btn move-btn list-btn">Movimentar</button>
              <button @click.stop="openEdit(entry.item)" class="action-btn edit-btn list-btn">Editar</button>
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
                  <span class="item-price">{{ currencySymbol(entry.item.sale_currency || entry.item.currency) }} {{ Number(entry.item.sale_price).toLocaleString('pt-BR', { minimumFractionDigits: 2 }) }}</span>
                </template>
              </div>
              <div v-if="entry.item.barcode" class="item-barcode-row">
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="10" height="10" style="flex-shrink:0"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9V5a2 2 0 012-2h2M3 15v4a2 2 0 002 2h2m10-18h2a2 2 0 012 2v4m0 10v4a2 2 0 01-2 2h-2M9 3h6M9 21h6" /></svg>
                <span class="item-barcode">{{ entry.item.barcode }}</span>
              </div>
              <div class="item-bottom-row">
                <div class="item-left-info">
                  <span class="stock-number" :class="'stock-' + entry.item.alert_level">
                    <template v-if="entry.item.stock_loja !== undefined">Loja:&nbsp;{{ entry.item.stock_loja }}&nbsp;·&nbsp;Dep.:&nbsp;{{ entry.item.stock_deposito ?? 0 }}</template>
                    <template v-else>Estoque:&nbsp;{{ entry.item.current_stock }}</template>
                  </span>
                  <span v-if="entry.item.size" class="item-size-inline">{{ entry.item.size }}</span>
                  <span v-if="entry.item.location" class="item-location-inline">· {{ entry.item.location }}</span>
                  <span v-if="entry.item.alert_level && entry.item.alert_level !== 'ok'" class="alert-badge" :class="'badge-' + entry.item.alert_level">{{ alertLabel(entry.item.alert_level) }}</span>
                </div>
                <div class="item-actions">
                  <div class="exit-wrap">
                    <button @click.stop="confirmExitId = entry.item.id" class="action-btn exit-btn" :disabled="entry.item.current_stock <= 0">−1</button>
                    <div v-if="confirmExitId === entry.item.id" class="exit-confirm-popover">
                      <template v-if="exitLocations(entry.item).loja && exitLocations(entry.item).deposito">
                        <span class="confirm-question">Retirar de:</span>
                        <button @click.stop="handleQuickExit(entry.item, 'loja')" class="confirm-loc confirm-loja">Loja ({{ entry.item.stock_loja }})</button>
                        <button @click.stop="handleQuickExit(entry.item, 'deposito')" class="confirm-loc confirm-dep">Dep. ({{ entry.item.stock_deposito }})</button>
                      </template>
                      <template v-else-if="exitLocations(entry.item).deposito">
                        <span class="confirm-question">Retirar do Depósito?</span>
                        <button @click.stop="handleQuickExit(entry.item, 'deposito')" class="confirm-yes">Sim</button>
                      </template>
                      <template v-else>
                        <span class="confirm-question">Retirar da Loja?</span>
                        <button @click.stop="handleQuickExit(entry.item, 'loja')" class="confirm-yes">Sim</button>
                      </template>
                      <button @click.stop="confirmExitId = null" class="confirm-no">×</button>
                    </div>
                  </div>
                  <button @click.stop="openMovement(entry.item)" class="action-btn move-btn">Movimentar</button>
                  <button @click.stop="openEdit(entry.item)" class="action-btn edit-btn">Editar</button>
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
              <span class="item-extra-label">Limites</span>
              <span class="item-extra-val">mín {{ entry.item.min_stock }} · máx {{ entry.item.max_stock }}</span>
            </div>
            <div v-if="Number(entry.item.cost_price) > 0" class="item-extra-row">
              <span class="item-extra-label">Custo</span>
              <span class="item-extra-val">{{ currencySymbol(entry.item.cost_currency || entry.item.currency) }} {{ Number(entry.item.cost_price).toLocaleString('pt-BR', { minimumFractionDigits: 2 }) }}</span>
            </div>
            <div v-if="entry.item.description" class="item-extra-row">
              <span class="item-extra-label">Descrição</span>
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
      <button class="image-modal-close" @click="imageModalSrc = null">✕</button>
    </div>

    <!-- Toast -->
    <div v-if="toast" class="toast" :class="'toast-' + toast.type">{{ toast.message }}</div>

    <!-- Modals -->
    <BarcodeScanner v-if="showScanner" @barcode-detected="onBarcodeDetected" @close="showScanner = false" />

    <ItemFormModal
      v-if="showItemForm"
      :item="editingItem"
      :suppliers="suppliers"
      :existing-group-keys="existingGroupKeys"
      :existing-brands="existingBrands"
      @saved="onItemSaved"
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
      @imported="() => { reloadItems(); inventoryStore.loadAlerts() }"
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

    <!-- Barra flutuante de seleção -->
    <transition name="sel-bar">
      <div v-if="selectionMode && selectedIds.length > 0 && !showBulkEdit" class="selection-bar">
        <span class="sel-count">{{ selectedIds.length }} item{{ selectedIds.length !== 1 ? 's' : '' }} selecionado{{ selectedIds.length !== 1 ? 's' : '' }}</span>
        <div class="sel-actions">
          <button @click="showGroupModal = true" class="sel-btn sel-btn-primary">Agrupar</button>
          <button @click="openBulkEdit" class="sel-btn sel-btn-primary">
            <span class="sel-label-full">Editar massivo</span>
            <span class="sel-label-short">Editar</span>
          </button>
          <button @click="openBulkTransfer" class="sel-btn sel-btn-transfer">
            <span class="sel-label-full">Transferir</span>
            <span class="sel-label-short">Transf.</span>
          </button>
          <button @click="selectAll" class="sel-btn">
            <span class="sel-label-full">Sel. todos</span>
            <span class="sel-label-short">Todos</span>
          </button>
          <button @click="selectedIds = []" class="sel-btn">Limpar</button>
        </div>
      </div>
    </transition>

    <!-- Modal de nome do grupo -->
    <div v-if="showGroupModal" class="gmodal-overlay" @click.self="showGroupModal = false">
      <div class="gmodal">
        <h3 class="gmodal-title">Definir nome do grupo</h3>
        <p class="gmodal-sub">
          {{ selectedUngrouped.length }} ite{{ selectedUngrouped.length !== 1 ? 'ns' : 'm' }} serão agrupados. Defina um código ou nome de modelo:
        </p>
        <!-- Warning: some selected items are already in a group -->
        <div v-if="selectedAlreadyGrouped.length > 0" class="gmodal-warn">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="14" height="14" style="flex-shrink:0"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>
          {{ selectedAlreadyGrouped.length }} item{{ selectedAlreadyGrouped.length !== 1 ? 'ns' : '' }} já
          {{ selectedAlreadyGrouped.length !== 1 ? 'pertencem' : 'pertence' }} a um grupo e
          {{ selectedAlreadyGrouped.length !== 1 ? 'serão ignorados' : 'será ignorado' }}.
        </div>
        <div v-if="selectedUngrouped.length < 2" class="gmodal-error">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="14" height="14" style="flex-shrink:0"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
          Selecione pelo menos 2 itens sem grupo para poder agrupar.
        </div>
        <input
          v-model="groupNameInput"
          type="text"
          class="gmodal-input"
          placeholder="Ex: DKR003, FLC009 LUTT/NAPA..."
          list="gname-list"
          ref="groupNameInputRef"
          @keydown.enter="confirmGroup"
          :disabled="selectedUngrouped.length < 2"
        />
        <datalist id="gname-list">
          <option v-for="gk in existingGroupKeys" :key="gk" :value="gk" />
        </datalist>
        <p class="gmodal-hint">Sugestão baseada nos nomes: <strong>{{ groupNameSuggestion }}</strong></p>
        <div class="gmodal-footer">
          <button @click="showGroupModal = false" class="sel-btn">Cancelar</button>
          <button @click="confirmGroup" class="sel-btn sel-btn-primary"
            :disabled="!groupNameInput.trim() || grouping || selectedUngrouped.length < 2">
            {{ grouping ? 'Agrupando...' : `Agrupar ${selectedUngrouped.length}` }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useInventoryStore } from '@/stores/inventory'
import { inventoryAPI, type InventoryItem, type GroupResponse, type SuggestionResponse } from '@/services/api'
import BarcodeScanner from '@/components/inventory/BarcodeScanner.vue'
import ItemFormModal from '@/components/inventory/ItemFormModal.vue'
import MovementModal from '@/components/inventory/MovementModal.vue'
import ImportModal from '@/components/inventory/ImportModal.vue'
import BulkEditModal from '@/components/inventory/BulkEditModal.vue'
import BulkTransferModal from '@/components/inventory/BulkTransferModal.vue'
import GroupingSuggestionModal from '@/components/inventory/GroupingSuggestionModal.vue'
import LabelTemplatesModal from '@/components/inventory/LabelTemplatesModal.vue'

const route = useRoute()
const inventoryStore = useInventoryStore()

const searchQuery = ref('')
const activeStatus = ref((route.query.status as string) || '')
const showScanner = ref(false)
const showItemForm = ref(false)
const showMovementModal = ref(false)
const showImport = ref(false)
const showLabelTemplates = ref(false)
const editingItem = ref<InventoryItem | null>(null)
const movementItem = ref<InventoryItem | null>(null)
const suppliers = ref<Array<{ id: string; name: string }>>([])
const toast = ref<{ message: string; type: string } | null>(null)
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
    ? distinctBrands.value.filter(b => b.toLowerCase().includes(brandSearch.value.toLowerCase()))
    : distinctBrands.value
)
const filteredCategories = computed(() =>
  categorySearch.value.trim()
    ? distinctCategories.value.filter(c => c.toLowerCase().includes(categorySearch.value.toLowerCase()))
    : distinctCategories.value
)
const expandedCardIds = ref<string[]>([])
const confirmRemoveChip = ref<string | null>(null)

const backendGroups = ref<GroupResponse[]>([])
const backendSuggestions = ref<SuggestionResponse[]>([])
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
const confirmExitId = ref<string | null>(null)
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
  try {
    backendGroups.value = await inventoryAPI.getGroups(params)
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
  try {
    backendSuggestions.value = await inventoryAPI.getSuggestions()
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

function onItemPointerDown(itemId: string, e: PointerEvent) {
  if (!selectionMode.value) return
  // Don't trigger from buttons/links inside the card
  if ((e.target as HTMLElement).closest('button, a')) return
  if (e.pointerType === 'mouse' && e.button !== 0) return

  const startX = e.clientX
  const startY = e.clientY
  let dragged = false

  const onMove = (ev: PointerEvent) => {
    if (Math.hypot(ev.clientX - startX, ev.clientY - startY) < 10) return
    ev.preventDefault() // prevent scroll on touch while drag-selecting

    if (!dragged) {
      dragged = true
      isDragSelecting.value = true
      // Ensure the starting item is selected
      if (!selectedIds.value.includes(itemId)) selectedIds.value.push(itemId)
    }

    const el = document.elementFromPoint(ev.clientX, ev.clientY)
    const card = el?.closest('[data-item-id]') as HTMLElement | null
    const id = card?.dataset.itemId
    if (id && !selectedIds.value.includes(id)) selectedIds.value.push(id)
  }

  const onUp = () => {
    document.removeEventListener('pointermove', onMove)
    document.removeEventListener('pointerup', onUp)
    isDragSelecting.value = false
    if (dragged) {
      // Suppress the click that fires right after pointerup so it doesn't toggle off
      document.addEventListener('click', (ev) => {
        ev.stopPropagation()
        ev.preventDefault()
      }, { capture: true, once: true })
    }
  }

  document.addEventListener('pointermove', onMove, { passive: false })
  document.addEventListener('pointerup', onUp)
}

function selectAll() {
  const all = new Set<string>()
  for (const item of inventoryStore.items) all.add(item.id)
  for (const g of backendGroups.value) {
    for (const item of g.items) all.add(item.id)
  }
  selectedIds.value = [...all]
}

const selectedItemsForBulkEdit = ref<InventoryItem[]>([])

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
    groupNameInput.value = groupNameSuggestion.value
    nextTick(() => groupNameInputRef.value?.focus())
  }
})

async function confirmGroup() {
  const name = groupNameInput.value.trim()
  if (!name || grouping.value) return
  const idsToGroup = selectedUngrouped.value.map(i => i.id)
  if (idsToGroup.length < 2) return
  grouping.value = true
  try {
    await inventoryAPI.groupItems(idsToGroup, name)
    showToast(`${idsToGroup.length} itens agrupados como "${name}"`, 'success')
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
  total_stock: number
}

type FlatEntry = { type: 'group'; group: GroupEntry } | { type: 'item'; item: InventoryItem }

const flatList = computed<FlatEntry[]>(() => {
  if (!groupMode.value) {
    return inventoryStore.items.map(item => ({ type: 'item' as const, item }))
  }

  // Em modo grupo: backendGroups já vem filtrado pelo backend quando há busca
  const term = searchQuery.value.toLowerCase().trim()
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

function groupAlertLevel(items: InventoryItem[]): string {
  if (items.some(i => i.alert_level === 'out')) return 'out'
  if (items.some(i => i.alert_level === 'low')) return 'low'
  if (items.some(i => i.alert_level === 'high')) return 'high'
  return 'ok'
}

/** Returns 'deposito' if ALL stock is in depósito, 'loja' if all in loja, 'mixed' otherwise. */
function groupLocationBadge(items: InventoryItem[]): 'deposito' | 'loja' | 'mixed' | null {
  const hasStock = items.some(i => i.current_stock > 0)
  if (!hasStock) return null
  if (items.every(i => (i.stock_loja ?? 0) === 0)) return 'deposito'
  if (items.every(i => (i.stock_deposito ?? 0) === 0)) return 'loja'
  return 'mixed'
}

const existingGroupKeys = computed<string[]>(() =>
  backendGroups.value.map(g => g.group_key).sort()
)

const existingBrands = computed<string[]>(() => {
  const s = new Set<string>()
  for (const item of inventoryStore.items) {
    if (item.brand) s.add(item.brand)
  }
  return Array.from(s).sort()
})

// ── Size ordering ────────────────────────────────────────────────────────────
const LETTER_SIZE_ORDER: Record<string, number> = {
  PP: 0, P: 1, M: 2, G: 3, GG: 4, XG: 5, XGG: 6, XXG: 7, XXXG: 8, U: 9
}
function sizeSortKey(size?: string | null): [number, number, string] {
  if (!size) return [3, 0, '']
  const s = size.trim().toUpperCase()
  if (s in LETTER_SIZE_ORDER) return [1, LETTER_SIZE_ORDER[s], s]
  const n = parseFloat(s)
  if (!isNaN(n)) return [0, n, s]
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
  editingGroupName.value = groupKey
  nextTick(() => {
    const input = document.querySelector<HTMLInputElement>('.group-name-input')
    input?.focus()
    input?.select()
  })
}

async function saveGroupName(oldKey: string) {
  const newKey = editingGroupName.value.trim()
  editingGroupKey.value = null
  if (!newKey || newKey === oldKey) return
  try {
    await inventoryAPI.renameGroup(oldKey, newKey)
    showToast(`Grupo renomeado para "${newKey}"`, 'success')
    await Promise.all([reloadItems(), loadGroupsFiltered()])
  } catch (e: any) {
    showToast(e.response?.data?.detail || 'Erro ao renomear grupo', 'error')
  }
}

async function handleUngroup(groupKey: string) {
  try {
    await inventoryAPI.ungroup(groupKey)
    showToast(`Grupo "${groupKey}" desagrupado`, 'success')
    await Promise.all([reloadItems(), loadGroups()])
  } catch (e: any) {
    showToast(e.response?.data?.detail || 'Erro ao desagrupar', 'error')
  }
}

async function removeItemFromGroup(itemId: string, groupKey: string) {
  try {
    await inventoryAPI.removeFromGroup(itemId)
    showToast(`Item removido do grupo "${groupKey}"`, 'success')
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
])

let searchTimer: ReturnType<typeof setTimeout> | null = null
watch(searchQuery, (val) => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    const trimmed = val.trim()
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

function applyAdvancedFilter() {
  inventoryStore.filters.brand = filterBrand.value
  inventoryStore.filters.category = filterCategory.value
  reloadItems()
}

function clearAdvancedFilters() {
  filterBrand.value = ''
  filterCategory.value = ''
  inventoryStore.filters.brand = ''
  inventoryStore.filters.category = ''
  reloadItems()
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
  showToast(`${count} itens agrupados como "${groupKey}"`, 'success')
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

function openMovement(item: InventoryItem) {
  movementItem.value = item
  showMovementModal.value = true
}

async function handleQuickExit(item: InventoryItem, location: string = 'loja') {
  confirmExitId.value = null
  try {
    const result = await inventoryStore.quickExit(item.id, location)
    const loc = location === 'deposito' ? 'Depósito' : 'Loja'
    showToast(`Saída (${loc}) registrada. Estoque: ${result.new_stock}`, 'success')
  } catch (e: any) {
    showToast(e.response?.data?.detail || 'Erro ao registrar saída', 'error')
  }
}

/** Retorna quais locais têm estoque disponível para saída rápida */
function exitLocations(item: InventoryItem): { loja: boolean; deposito: boolean } {
  const hasLoja = (item.stock_loja ?? 0) > 0
  const hasDeposito = (item.stock_deposito ?? 0) > 0
  if (hasLoja || hasDeposito) return { loja: hasLoja, deposito: hasDeposito }
  return { loja: true, deposito: false } // fallback sem info de split
}

function onBarcodeDetected(code: string) {
  showScanner.value = false
  searchQuery.value = code
}

function onItemSaved(item: InventoryItem) {
  showItemForm.value = false
  showToast(`Item "${item.name}" salvo com sucesso`, 'success')
  reloadItems()
}

function onMovementSaved() {
  showMovementModal.value = false
  showToast('Movimentação registrada', 'success')
  reloadItems()
}

async function onBulkEditSaved() {
  showBulkEdit.value = false
  selectionMode.value = false
  selectedIds.value = []
  showToast('Itens atualizados com sucesso', 'success')
  await Promise.all([reloadItems(), loadGroupsFiltered()])
}

async function onBulkTransferSaved() {
  showBulkTransfer.value = false
  selectionMode.value = false
  selectedIds.value = []
  showToast('Transferência realizada com sucesso', 'success')
  reloadItems()
}

function alertLabel(level: string | undefined) {
  const labels: Record<string, string> = {
    out: 'Sem estoque', low: 'Baixo', high: 'Excesso', ok: 'OK', inactive: 'Inativo'
  }
  return labels[level || 'ok'] || 'OK'
}

function showToast(message: string, type: string) {
  toast.value = { message, type }
  setTimeout(() => { toast.value = null }, 3000)
}

function onDocClick(e: MouseEvent) {
  if (filterChipsRef.value && !filterChipsRef.value.contains(e.target as Node)) {
    openFilter.value = null
    brandSearch.value = ''
    categorySearch.value = ''
  }
  const target = e.target as HTMLElement
  if (!target.closest('.exit-wrap')) {
    confirmExitId.value = null
  }
  if (!target.closest('.chip-remove-wrap')) {
    confirmRemoveChip.value = null
  }
}

onUnmounted(() => {
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
    distinctBrands.value = dv.brands
    distinctCategories.value = dv.categories
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
.inventory-view { min-height: 100vh; background: #f9fafb; }
.sticky-toolbar { position: sticky; top: 0; z-index: 30; background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.page-header { background: white; border-bottom: 1px solid #e5e7eb; padding: 1rem; }
.header-content { display: flex; align-items: center; justify-content: space-between; padding: 0 1rem; }
.header-right { display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0; }
.header-top { display: flex; align-items: center; gap: 0.75rem; }
.back-button { background: none; border: none; cursor: pointer; color: #6b7280; padding: 0.25rem; }
.page-title { font-size: 1.25rem; font-weight: 700; color: #111827; margin: 0; }
.page-subtitle { font-size: 0.8rem; color: #6b7280; margin: 0.25rem 0 0 2.25rem; }
.btn { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.875rem; cursor: pointer; border: none; font-weight: 500; }
.btn-primary { background: #3b82f6; color: white; }
.btn-secondary { background: white; color: #374151; border: 1px solid #d1d5db; }
@media (max-width: 600px) {
  .page-header { padding: 0.4rem 0.75rem; }
  .header-content { padding: 0; }
  .page-subtitle { display: none; }
  .page-title { font-size: 1rem; }
  .header-top { gap: 0.5rem; }
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
  padding: 0 1rem 1rem;
}

/* --- COMPACT view (default, 2 cols) --- */
.view-compact {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
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
.view-grid .item-actions { flex-wrap: wrap; gap: 0.25rem; }
.view-grid .action-btn { font-size: 0.68rem; padding: 0.25rem 0.45rem; }

@media (max-width: 600px) {
  .view-compact { grid-template-columns: 1fr; }
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
.exp-exit { background: #fef3c7; color: #b45309; }
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
.item-bottom-row { display: flex; align-items: center; justify-content: space-between; gap: 0.4rem; margin-top: 0.1rem; }
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
.item-actions { display: flex; gap: 0.3rem; flex-shrink: 0; }
.action-btn { padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.7rem; cursor: pointer; border: none; font-weight: 600; white-space: nowrap; }
.exit-btn  { background: #fee2e2; color: #dc2626; }
.exit-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.move-btn  { background: #dbeafe; color: #1d4ed8; }
.edit-btn  { background: #f3f4f6; color: #374151; }

/* ── Quick exit confirm popover ──────────────────────────────────────────── */
.exit-wrap { position: relative; display: inline-block; }
.exit-confirm-popover {
  position: absolute;
  bottom: calc(100% + 7px);
  left: 50%;
  transform: translateX(-50%);
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 9px;
  padding: 0.45rem 0.55rem;
  box-shadow: 0 6px 18px rgba(0,0,0,0.13);
  z-index: 60;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  white-space: nowrap;
}
.exit-confirm-popover::before {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: #e5e7eb;
}
.exit-confirm-popover::after {
  content: '';
  position: absolute;
  top: calc(100% - 1px);
  left: 50%;
  transform: translateX(-50%);
  border: 5px solid transparent;
  border-top-color: white;
}
.confirm-question { font-size: 0.72rem; color: #374151; font-weight: 500; }
.confirm-yes { background: #ef4444; color: white; border: none; border-radius: 5px; padding: 0.2rem 0.55rem; font-size: 0.7rem; cursor: pointer; font-weight: 700; }
.confirm-yes:hover { background: #dc2626; }
.confirm-no { background: #f3f4f6; color: #6b7280; border: none; border-radius: 5px; padding: 0.2rem 0.45rem; font-size: 0.72rem; cursor: pointer; font-weight: 700; line-height: 1; }
.confirm-no:hover { background: #e5e7eb; }
.confirm-loc { border: none; border-radius: 5px; padding: 0.22rem 0.55rem; font-size: 0.7rem; cursor: pointer; font-weight: 700; transition: opacity 0.12s; }
.confirm-loja { background: #dcfce7; color: #15803d; }
.confirm-loja:hover { background: #bbf7d0; }
.confirm-dep { background: #ede9fe; color: #6d28d9; }
.confirm-dep:hover { background: #ddd6fe; }

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
.card-check { position: absolute; top: 0.35rem; left: 0.35rem; z-index: 2; }
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
</style>
