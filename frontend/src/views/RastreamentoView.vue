<template>
  <div class="rastreamento-page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-content">
        <div class="header-left">
          <button @click="$router.replace('/dashboard')" class="back-button">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div class="header-info">
            <h1 class="page-title">Rastreamento de Encomendas</h1>
            <p class="page-subtitle">Gerencie e acompanhe todas as suas entregas</p>
          </div>
        </div>
        
        <div class="header-actions">
          
          <button @click="abrirModalCriacao" class="btn btn-primary">
            <svg class="btn-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
          </button>
        </div>
      </div>
    </header>

    <!-- Stats Cards -->
    <div class="stats-section">
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon blue">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2M4 13h2m0 0V9a2 2 0 012-2h2a2 2 0 012 2v4m-6 0h6" />
            </svg>
          </div>
          <div class="stat-content">
            <p class="stat-label">Total</p>
            <p class="stat-value">{{ resumo?.total_rastreamentos || 0 }}</p>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon yellow">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div class="stat-content">
            <p class="stat-label">Trânsito</p>
            <p class="stat-value">{{ resumo?.em_transito || 0 }}</p>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon green">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <div class="stat-content">
            <p class="stat-label">Entregues</p>
            <p class="stat-value">{{ resumo?.entregues || 0 }}</p>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon red">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div class="stat-content">
            <p class="stat-label">Pendentes</p>
            <p class="stat-value">{{ resumo?.pendentes || 0 }}</p>
          </div>
        </div>
      </div>
    </div>
    
    <!-- CALCULADORA DE FRETE DESATIVADA — reativar quando API estiver pronta
    <div class="freight-section"> ... </div>
    -->

    <!-- Filtros e Busca -->
    <div class="filters-section">
      <div class="filters-content">
        <div class="search-box">
          <svg class="search-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input 
            v-model="filtros.busca"
            type="text" 
            placeholder="Buscar por código ou destinatário..."
            class="search-input"
            @input="aplicarFiltros"
          />
        </div>

        <div class="filter-select">
          <select v-model="filtros.status" @change="aplicarFiltros" class="status-select">
            <option value="">Todos os Status</option>
            <option value="PENDENTE">Pendente</option>
            <option value="EM_TRANSITO">Em Trânsito</option>
            <option value="ENTREGUE">Entregue</option>
            <option value="ERRO">Erro</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="loading-section">
      <div class="loading-spinner">
        <svg class="spinner" fill="none" viewBox="0 0 24 24">
          <circle class="spinner-track" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="spinner-path" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      </div>
      <p>Carregando rastreamentos...</p>
    </div>

    <!-- Lista de Rastreamentos -->
    <div v-else class="rastreamentos-section">
      <div v-if="rastreamentosFiltrados.length === 0" class="empty-state">
        <svg class="empty-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2M4 13h2m0 0V9a2 2 0 012-2h2a2 2 0 012 2v4m-6 0h6" />
        </svg>
        <h3>Nenhum rastreamento encontrado</h3>
        <p>Adicione um novo rastreamento para começar</p>
        <button @click="abrirModalCriacao" class="btn btn-primary">
          Adicionar Rastreamento
        </button>
      </div>

      <div v-else class="rastreamentos-list">
        <!-- Cabeçalho da lista desktop -->
        <div class="list-header desktop-header">
          <div class="header-codigo">Código</div>
          <div class="header-destinatario">Destinatário</div>
          <div class="header-descricao">Descrição</div>
          <div class="header-rastreio">Último evento</div>
          <div class="header-status">Status</div>
          <div class="header-data">Data</div>
          <div class="header-actions">Ações</div>
        </div>

        <div
          v-for="rastreamento in rastreamentosFiltrados"
          :key="rastreamento.id"
          class="mobile-rastreamento-row"
          :class="['mobile-rastreamento-row-status-' + rastreamento.status.toLowerCase().replace('_', '-'), { 'card-flash': flashedIds.has(rastreamento.id) }]"
        >
          <!-- Layout Mobile: Card Dropdown -->
          <div class="mobile-dropdown-card">
              <!-- Cabeçalho sempre visível -->
              <div
                class="mobile-card-header"
                @click="toggleCard(rastreamento.id)"
              >
                <!-- Linha 1: Nome + Badge + Chevron -->
                <div class="mch-top">
                  <div class="mch-name-wrap">
                    <span class="mch-name">{{ (rastreamento.pedido_id && rastreamento.cliente_nome) ? rastreamento.cliente_nome : (rastreamento.destinatario || 'Sem destinatário') }}</span>
                    <button v-if="rastreamento.pedido_id" class="mch-pedido-badge mch-pedido-btn" @click.stop="goToPedido(rastreamento)">#{{ rastreamento.numero_pedido || rastreamento.pedido_id.slice(0, 8) }}</button>
                  </div>
                  <span class="status-badge-inline mch-badge" :class="getStatusBadgeClass(rastreamento.status)">{{ getStatusText(rastreamento.status) }}</span>
                  <div class="mobile-expand-icon">
                    <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" :class="{ 'rotate-180': isCardExpanded(rastreamento.id) }">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </div>
                <!-- Linha 2: Código + Serviço + Copiar -->
                <div class="mch-code-row">
                  <span class="mobile-code">{{ rastreamento.codigo_rastreio }}</span>
                  <span v-if="getBadgeText(rastreamento.rastreio_info)" class="mch-service">{{ getBadgeText(rastreamento.rastreio_info) }}</span>
                  <button @click.stop="copiarCodigo(rastreamento)" class="mobile-copy-btn" title="Copiar">
                    <svg width="10" height="10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  </button>
                </div>
                <!-- Linha 3: Descrição sutil -->
                <p v-if="rastreamento.descricao" class="mch-desc">{{ rastreamento.descricao }}</p>
                <!-- Barra de progresso sutil -->
                <div class="mch-progress">
                  <div
                    class="mch-progress-fill"
                    :class="'mpf-' + rastreamento.status.toLowerCase().replace('_', '-')"
                    :style="{ width: (rastreamento.status === 'ERRO' || rastreamento.status === 'NAO_ENCONTRADO') ? '5%' : ((trackingProgressStep(rastreamento) / 4) * 100) + '%' }"
                  ></div>
                </div>
              </div>
              
              <!-- Conteúdo expansível -->
              <div 
                class="mobile-card-content"
                :class="{ 'expanded': isCardExpanded(rastreamento.id) }"
              >
                <div class="mobile-card-inner">
                  <!-- Status -->
                  <div class="mobile-content-row">
                    <span class="mobile-content-label">Status:</span>
                    <span class="status-badge-inline" :class="getStatusBadgeClass(rastreamento.status)">
                      {{ getStatusText(rastreamento.status) }}
                    </span>
                  </div>
                  
                  <!-- Detalhes -->
                  <div v-if="rastreamento.pedido_id" class="mobile-content-row">
                    <span class="mobile-content-label">Pedido:</span>
                    <button class="mobile-content-value pedido-link-badge pedido-link-btn" @click.stop="goToPedido(rastreamento)">#{{ rastreamento.numero_pedido || rastreamento.pedido_id.slice(0,8) }}</button>
                  </div>
                  <div class="mobile-content-row" v-if="rastreamento.destinatario">
                    <span class="mobile-content-label">Destinatário:</span>
                    <span class="mobile-content-value">{{ rastreamento.destinatario }}</span>
                  </div>
                  <div class="mobile-content-row" v-if="rastreamento.descricao">
                    <span class="mobile-content-label">Descrição:</span>
                    <span class="mobile-content-value">{{ rastreamento.descricao }}</span>
                  </div>
                  <div class="mobile-content-row">
                    <span class="mobile-content-label">Criado em:</span>
                    <span class="mobile-content-value mobile-date-value">{{ formatarData(rastreamento.created_at) }}</span>
                  </div>
                  <div v-if="formatUltimaAtt(rastreamento)" class="mobile-content-row">
                    <span class="mobile-content-label">Última att.:</span>
                    <span class="mobile-content-value ultima-att-value">{{ formatUltimaAtt(rastreamento) }}</span>
                  </div>
                  
                  <!-- Rastreio info (service + expected delivery) -->
                  <div v-if="rastreamento.rastreio_info && (getBadgeText(rastreamento.rastreio_info) || rastreamento.rastreio_info.data_prevista)" class="rastreio-info-bar">
                    <span v-if="getBadgeText(rastreamento.rastreio_info)" class="ri-badge">
                      {{ getBadgeText(rastreamento.rastreio_info) }}
                    </span>
                    <span v-if="rastreamento.rastreio_info.data_prevista" class="ri-previsao">
                      Prev. entrega: <strong>{{ rastreamento.rastreio_info.data_prevista }}</strong>
                    </span>
                    <span v-if="rastreamento.rastreio_info.atrasado" class="ri-atrasado">Atrasado</span>
                  </div>

                  <!-- Progress track -->
                  <div class="progress-track" :class="{ 'track-erro': rastreamento.status === 'ERRO' || rastreamento.status === 'NAO_ENCONTRADO' }">
                    <div class="track-steps">
                      <div v-for="(step, i) in ['Postado','Em trânsito','Saiu p/ entrega','Entregue']" :key="i" class="track-step">
                        <div class="step-dot" :class="trackingProgressStep(rastreamento) > i ? 'dot-done' : (trackingProgressStep(rastreamento) === i+1 ? 'dot-active' : 'dot-future')"></div>
                        <span class="step-label">{{ step }}</span>
                      </div>
                    </div>
                    <div class="track-bar">
                      <div class="track-fill" :style="{ width: rastreamento.status === 'ERRO' || rastreamento.status === 'NAO_ENCONTRADO' ? '0%' : ((trackingProgressStep(rastreamento) - 1) / 3 * 100) + '%' }"></div>
                    </div>
                  </div>

                  <!-- Ações -->
                  <div class="mobile-content-actions">
                    <button
                      @click="editarRastreamento(rastreamento)"
                      class="mobile-action-btn-expanded edit"
                      title="Editar"
                    >
                      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                      Editar
                    </button>
                    <button
                      @click="removerRastreamento(rastreamento)"
                      class="mobile-action-btn-expanded delete"
                      title="Excluir"
                    >
                      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                      Excluir
                    </button>
                    <button
                      @click.stop="atualizarOnline(rastreamento)"
                      :disabled="isRefreshing(rastreamento.id)"
                      class="mobile-action-btn-expanded refresh"
                      title="Atualizar via API"
                    >
                      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" :class="{ 'spin': isRefreshing(rastreamento.id) }">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                      {{ isRefreshing(rastreamento.id) ? 'Atualizando...' : 'Atualizar' }}
                    </button>
                  </div>

                  <!-- Events timeline -->
                  <div v-if="rastreamento.historico_eventos?.length" class="events-timeline">
                    <p class="timeline-title">Histórico de eventos</p>
                    <div class="timeline-list">
                      <div v-for="(ev, idx) in rastreamento.historico_eventos" :key="idx" class="timeline-event">
                        <div class="tl-dot" :class="idx === 0 ? 'tl-dot-active' : ''"></div>
                        <div class="tl-content">
                          <p class="tl-situacao">{{ ev.situacao }}</p>
                          <p v-if="ev.situacao_frontend && ev.situacao_frontend !== ev.situacao" class="tl-situacao-sub">{{ ev.situacao_frontend }}</p>
                          <p class="tl-meta">
                            <span v-if="ev.local">{{ ev.local }}</span>
                            <span v-if="ev.local_tipo" class="tl-local-tipo"> ({{ ev.local_tipo }})</span>
                            <span v-if="(ev.local || ev.local_tipo) && ev.data"> · </span>
                            <span v-if="ev.data">{{ formatEventDate(ev.data) }}</span>
                          </p>
                          <p v-if="ev.destino_cidade" class="tl-destino">
                            → {{ ev.destino_cidade }}<span v-if="ev.destino_uf">/{{ ev.destino_uf }}</span>
                          </p>
                          <p v-if="ev.detalhes" class="tl-detalhe">{{ ev.detalhes }}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
          </div>
            
          <!-- Desktop layout -->
          <div class="rastreamento-row" @click="toggleCard(rastreamento.id)" style="cursor:pointer;">
          <div class="row-codigo desktop-only">
            <span class="codigo-text">{{ rastreamento.codigo_rastreio }}</span>
            <button 
              @click="copiarCodigo(rastreamento)"
              class="copy-btn"
              title="Copiar Código"
            >
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </button>

          </div>

          <!-- Destinatário + Pedido -->
          <div class="row-destinatario">
            <span class="row-dest-name">{{ (rastreamento.pedido_id && rastreamento.cliente_nome) ? rastreamento.cliente_nome : (rastreamento.destinatario || '-') }}</span>
            <button v-if="rastreamento.pedido_id" class="pedido-link-badge pedido-link-btn" @click.stop="goToPedido(rastreamento)">#{{ rastreamento.numero_pedido || '?' }}</button>
          </div>

          <!-- Descrição -->
          <div class="row-descricao">
            {{ rastreamento.descricao || '-' }}
          </div>

          <!-- Último evento + serviço -->
          <div class="row-rastreio row-ultimo-evento">
            <span v-if="getBadgeText(rastreamento.rastreio_info)" class="desktop-service-badge">{{ getBadgeText(rastreamento.rastreio_info) }}</span>
            <span class="ultimo-evento-text">
              {{ rastreamento.historico_eventos?.[0]?.situacao || '—' }}
            </span>
            <span v-if="rastreamento.rastreio_info?.data_prevista" class="desktop-previsao">Prev. {{ rastreamento.rastreio_info.data_prevista }}</span>
          </div>

          <!-- Status (badge estático) -->
          <div class="row-status">
            <span class="status-badge-inline" :class="getStatusBadgeClass(rastreamento.status)">
              {{ getStatusText(rastreamento.status) }}
            </span>
          </div>

          <!-- Data criação (desktop) -->
          <div class="row-data">
            <span>{{ formatarData(rastreamento.created_at) }}</span>
            <span v-if="formatUltimaAtt(rastreamento)" class="row-ultima-att">sync {{ formatUltimaAtt(rastreamento) }}</span>
          </div>

          <!-- Ações -->
          <div class="row-actions">
            <button
              @click="atualizarOnline(rastreamento)"
              :disabled="isRefreshing(rastreamento.id)"
              class="action-btn refresh"
              title="Atualizar via API"
            >
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" :class="{ 'spin': isRefreshing(rastreamento.id) }">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
            <button
              @click="editarRastreamento(rastreamento)"
              class="action-btn"
              title="Editar"
            >
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
            <button
              @click="removerRastreamento(rastreamento)"
              class="action-btn delete"
              title="Excluir"
            >
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
          </div>

          <!-- Desktop expanded detail panel -->
          <div v-if="isCardExpanded(rastreamento.id)" class="desktop-detail-panel">
            <!-- Service info bar -->
            <div v-if="rastreamento.rastreio_info && (getBadgeText(rastreamento.rastreio_info) || rastreamento.rastreio_info.data_prevista)" class="rastreio-info-bar">
              <span v-if="getBadgeText(rastreamento.rastreio_info)" class="ri-badge">{{ getBadgeText(rastreamento.rastreio_info) }}</span>
              <span v-if="rastreamento.rastreio_info.data_prevista" class="ri-previsao">Previsão de entrega: <strong>{{ rastreamento.rastreio_info.data_prevista }}</strong></span>
              <span v-if="rastreamento.rastreio_info.atrasado" class="ri-atrasado">Atrasado</span>
            </div>

            <div class="desktop-detail-body">
              <!-- Progress track -->
              <div class="progress-track" :class="{ 'track-erro': rastreamento.status === 'ERRO' || rastreamento.status === 'NAO_ENCONTRADO' }">
                <div class="track-steps">
                  <div v-for="(step, i) in ['Postado','Em trânsito','Saiu p/ entrega','Entregue']" :key="i" class="track-step">
                    <div class="step-dot" :class="trackingProgressStep(rastreamento) > i ? 'dot-done' : (trackingProgressStep(rastreamento) === i+1 ? 'dot-active' : 'dot-future')"></div>
                    <span class="step-label">{{ step }}</span>
                  </div>
                </div>
                <div class="track-bar">
                  <div class="track-fill" :style="{ width: rastreamento.status === 'ERRO' || rastreamento.status === 'NAO_ENCONTRADO' ? '0%' : ((trackingProgressStep(rastreamento) - 1) / 3 * 100) + '%' }"></div>
                </div>
              </div>

              <!-- Full timeline -->
              <div v-if="rastreamento.historico_eventos?.length" class="events-timeline desktop-timeline">
                <p class="timeline-title">Linha do tempo completa</p>
                <div class="timeline-list">
                  <div v-for="(ev, idx) in rastreamento.historico_eventos" :key="idx" class="timeline-event">
                    <div class="tl-dot" :class="idx === 0 ? 'tl-dot-active' : ''"></div>
                    <div class="tl-content">
                      <p class="tl-situacao">{{ ev.situacao }}</p>
                      <p v-if="ev.situacao_frontend && ev.situacao_frontend !== ev.situacao" class="tl-situacao-sub">{{ ev.situacao_frontend }}</p>
                      <p class="tl-meta">
                        <span v-if="ev.local">{{ ev.local }}</span>
                        <span v-if="ev.local_tipo" class="tl-local-tipo"> ({{ ev.local_tipo }})</span>
                        <span v-if="(ev.local || ev.local_tipo) && ev.data"> · </span>
                        <span v-if="ev.data">{{ formatEventDate(ev.data) }}</span>
                      </p>
                      <p v-if="ev.destino_cidade" class="tl-destino">
                        → {{ ev.destino_cidade }}<span v-if="ev.destino_uf">/{{ ev.destino_uf }}</span>
                      </p>
                      <p v-if="ev.detalhes" class="tl-detalhe">{{ ev.detalhes }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal de Criação/Edição -->
    <div v-if="showModal" class="modal-overlay" @click="fecharModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h2>{{ editandoRastreamento ? 'Editar' : 'Novo' }} Rastreamento</h2>
          <button @click="fecharModal" class="modal-close">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="modal-body">
          <div v-if="modalError" class="alert alert-error">
            {{ modalError }}
          </div>

          <div class="form-grid">

            <!-- Vincular Pedido -->
            <div class="form-group full-width">
              <label>Vincular Pedido (opcional)</label>
              <div style="position:relative;">
                <input
                  v-model="pedidoSearch"
                  type="text"
                  placeholder="Buscar nº pedido, descrição ou cliente..."
                  class="form-input"
                  @input="onPedidoSearchInput"
                  @focus="onPedidoFocus"
                  @blur="setTimeout(() => showPedidoSuggestions = false, 180)"
                  style="width:100%;box-sizing:border-box;"
                />
                <button
                  v-if="selectedPedido"
                  type="button"
                  @click="clearPedido"
                  style="position:absolute;right:.5rem;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;color:#9ca3af;font-size:.8rem;"
                >✕ Desvincular</button>
                <div v-if="showPedidoSuggestions" class="pedido-suggestion-list">
                  <button
                    v-for="p in pedidoSuggestions"
                    :key="p.id"
                    type="button"
                    class="pedido-suggestion-item"
                    @mousedown.prevent="selectPedido(p)"
                  >
                    <span class="sug-num">#{{ p.numero_pedido }}</span>
                    <span class="sug-info">{{ [p.cliente_nome, p.descricao].filter(Boolean).join(' · ') }}</span>
                  </button>
                </div>
              </div>
              <p v-if="selectedPedido" style="font-size:.72rem;color:#10b981;margin:.3rem 0 0;">
                ✓ Pedido #{{ selectedPedido.numero_pedido }} vinculado
              </p>
            </div>

            <div class="form-group full-width">
              <label for="codigo">Código de Rastreamento *</label>
              <input 
                id="codigo"
                ref="codigoInput"
                type="text" 
                v-model="formData.codigo_rastreio"
                placeholder="BR123456789BR"
                class="form-input codigo-input"
                @input="formatarCodigo"
                :maxlength="13"
                required
              />
              <small class="input-hint">Digite apenas letras e números</small>
            </div>

            <div class="form-group">
              <label for="destinatario">Destinatário</label>
              <input 
                id="destinatario"
                type="text" 
                v-model="formData.destinatario"
                placeholder="Nome do destinatário"
                class="form-input"
              />
            </div>

            <div class="form-group">
              <label for="descricao">Descrição</label>
              <input 
                id="descricao"
                type="text" 
                v-model="formData.descricao"
                placeholder="Descrição do objeto"
                class="form-input"
              />
            </div>

            <div class="form-group">
              <label for="origem">Origem</label>
              <input 
                id="origem"
                type="text" 
                v-model="formData.origem"
                placeholder="Local de origem"
                class="form-input"
              />
            </div>

            <div class="form-group">
              <label for="destino">Destino</label>
              <input
                id="destino"
                type="text"
                v-model="formData.destino"
                placeholder="Local de destino"
                class="form-input"
              />
            </div>

            <div class="form-group">
              <label for="custo_emissao">Custo de emissão (R$)</label>
              <input
                id="custo_emissao"
                type="number"
                step="0.01"
                min="0"
                v-model="formData.custo_emissao"
                placeholder="0,00"
                class="form-input"
              />
              <!-- modal-frete-hint desativado junto com a calculadora -->
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button @click="fecharModal" class="btn btn-secondary">
            Cancelar
          </button>
          
          <button 
            v-if="!editandoRastreamento"
            @click="consultarESalvar"
            :disabled="!formData.codigo_rastreio || salvando"
            class="btn btn-success"
          >
            <span v-if="salvando">Consultando...</span>
            <span v-else>Consultar e Salvar</span>
          </button>
          
          <button 
            @click="salvarRastreamento" 
            :disabled="!formData.codigo_rastreio || salvando" 
            class="btn btn-primary"
          >
            <span v-if="salvando">Salvando...</span>
            <span v-else>{{ editandoRastreamento ? 'Atualizar' : 'Salvar' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useRastreamentoStore } from '@/stores/rastreamento'
import type { Rastreamento, RastreamentoCreate } from '@/stores/rastreamento'
import { pedidosAPI, type Pedido } from '@/services/api'

const router = useRouter()
const route = useRoute()
const rastreamentoStore = useRastreamentoStore()

function goToPedido(rastreamento: Rastreamento) {
  if (rastreamento.pedido_id) {
    router.push({ path: '/pedidos', query: { pedido_id: rastreamento.pedido_id } })
  }
}

// Estado da página
const loading = ref(false)
const showModal = ref(false)
const salvando = ref(false)
const modalError = ref<string | null>(null)
const editandoRastreamento = ref<Rastreamento | null>(null)
const codigoInput = ref<HTMLInputElement>()
const expandedCards = ref<Set<string>>(new Set())
const refreshingIds = ref<Set<string>>(new Set())
const flashedIds = ref<Set<string>>(new Set())

// Pedido autocomplete
const pedidoSearch = ref('')
const pedidoSuggestions = ref<Pedido[]>([])
const pedidoCacheAll = ref<Pedido[]>([])
const selectedPedido = ref<Pedido | null>(null)
const showPedidoSuggestions = ref(false)

async function loadPedidoCache() {
  try { pedidoCacheAll.value = await pedidosAPI.getAll({ limit: 200 }) } catch { pedidoCacheAll.value = [] }
}

function onPedidoFocus() {
  if (!pedidoSearch.value) {
    pedidoSuggestions.value = pedidoCacheAll.value.slice(0, 8)
    showPedidoSuggestions.value = pedidoSuggestions.value.length > 0
  } else {
    onPedidoSearchInput()
  }
}

function onPedidoSearchInput() {
  const term = pedidoSearch.value.toLowerCase()
  if (!term) {
    pedidoSuggestions.value = pedidoCacheAll.value.slice(0, 8)
    showPedidoSuggestions.value = pedidoSuggestions.value.length > 0
    return
  }
  pedidoSuggestions.value = pedidoCacheAll.value.filter(p =>
    p.numero_pedido.toLowerCase().includes(term) ||
    (p.descricao || '').toLowerCase().includes(term) ||
    (p.cliente_nome || '').toLowerCase().includes(term)
  ).slice(0, 8)
  showPedidoSuggestions.value = pedidoSuggestions.value.length > 0
}

function selectPedido(p: Pedido) {
  selectedPedido.value = p
  formData.value.pedido_id = p.id
  pedidoSearch.value = `#${p.numero_pedido}${p.cliente_nome ? ' — ' + p.cliente_nome : ''}`
  showPedidoSuggestions.value = false
  // Auto-fill destinatário from pedido if empty
  if (!formData.value.destinatario && p.cliente_nome) {
    formData.value.destinatario = p.cliente_nome
  }
}

function clearPedido() {
  selectedPedido.value = null
  formData.value.pedido_id = undefined
  pedidoSearch.value = ''
}

function triggerFlash(id: string) {
  flashedIds.value = new Set([...flashedIds.value, id])
  setTimeout(() => {
    const s = new Set(flashedIds.value)
    s.delete(id)
    flashedIds.value = s
  }, 1200)
}

function formatUltimaAtt(r: any): string {
  if (!r.ultima_atualizacao) return ''
  try {
    const d = new Date(r.ultima_atualizacao)
    if (isNaN(d.getTime())) return ''
    return d.toLocaleDateString('pt-BR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch { return '' }
}

// Dados do resumo
const resumo = ref(rastreamentoStore.resumoDashboard)

// Filtros
const filtros = ref({
  busca: '',
  status: ''
})

// Form data
const formData = ref<RastreamentoCreate>({
  codigo_rastreio: '',
  descricao: '',
  destinatario: '',
  origem: '',
  destino: '',
  custo_emissao: undefined,
  pedido_id: undefined
})

// CALCULADORA DE FRETE DESATIVADA — reativar quando API estiver pronta
// const editingCepOrigem = ref(!localStorage.getItem('erp_cep_origem'))
// const calcCepOrigem = ref(localStorage.getItem('erp_cep_origem') || '')
// const calcCepDestino = ref('')
// const calcPeso = ref(0.3)
// const calcLoading = ref(false)
// const calcResultados = ref<any[]>([])
// const calcErro = ref('')
// const calcCustoParaUsar = ref<number | null>(null)
//
// function salvarCepOrigem() { ... }
// async function calcularFrete() { ... }
// function selecionarFrete(valor: string) { ... }

function getBadgeText(info: any): string {
  if (!info) return ''
  const tipo = info.tipo_servico || ''
  const match = tipo.match(/\(([^)]+)\)/)
  if (match) return match[1]
  return info.categoria || info.sigla || ''
}

// Computed
const rastreamentosFiltrados = computed(() => {
  let lista = rastreamentoStore.rastreamentosAtivos
  
  if (filtros.value.busca) {
    const busca = filtros.value.busca.toLowerCase()
    lista = lista.filter(r => 
      r.codigo_rastreio.toLowerCase().includes(busca) ||
      r.destinatario?.toLowerCase().includes(busca) ||
      r.descricao?.toLowerCase().includes(busca)
    )
  }
  
  if (filtros.value.status) {
    lista = lista.filter(r => r.status === filtros.value.status)
  }
  
  // Ordenação: entregues vão para o final, demais por data de criação (mais recentes primeiro)
  return lista.sort((a, b) => {
    // Se um é entregue e outro não, o entregue vai para baixo
    if (a.status === 'ENTREGUE' && b.status !== 'ENTREGUE') return 1
    if (a.status !== 'ENTREGUE' && b.status === 'ENTREGUE') return -1
    
    // Se ambos são entregues ou ambos não são, ordena por data de criação (mais recente primeiro)
    const dataA = new Date(a.created_at).getTime()
    const dataB = new Date(b.created_at).getTime()
    return dataB - dataA
  })
})

// Methods
async function carregarDados() {
  try {
    loading.value = true
    await Promise.all([
      rastreamentoStore.listarRastreamentos(),
      rastreamentoStore.obterResumoDashboard()
    ])
    resumo.value = rastreamentoStore.resumoDashboard
  } catch (error) {
    console.error('Erro ao carregar dados:', error)
  } finally {
    loading.value = false
  }
}

function aplicarFiltros() {
  // Os filtros são reativos através do computed
}

function abrirModalCriacao() {
  editandoRastreamento.value = null
  formData.value = {
    codigo_rastreio: '',
    descricao: '',
    destinatario: '',
    origem: '',
    destino: '',
    custo_emissao: undefined,
    pedido_id: undefined
  }
  selectedPedido.value = null
  pedidoSearch.value = ''
  modalError.value = null
  showModal.value = true
  loadPedidoCache()

  nextTick(() => {
    codigoInput.value?.focus()
  })
}

function editarRastreamento(rastreamento: Rastreamento) {
  triggerFlash(rastreamento.id)
  editandoRastreamento.value = rastreamento
  formData.value = {
    codigo_rastreio: rastreamento.codigo_rastreio,
    descricao: rastreamento.descricao || '',
    destinatario: rastreamento.destinatario || '',
    origem: rastreamento.origem || '',
    destino: rastreamento.destino || '',
    custo_emissao: rastreamento.custo_emissao,
    pedido_id: rastreamento.pedido_id
  }
  // Restore pedido search field if linked
  if (rastreamento.pedido_id && rastreamento.numero_pedido) {
    pedidoSearch.value = `#${rastreamento.numero_pedido}${rastreamento.cliente_nome ? ' — ' + rastreamento.cliente_nome : ''}`
    selectedPedido.value = { id: rastreamento.pedido_id, numero_pedido: rastreamento.numero_pedido, cliente_nome: rastreamento.cliente_nome } as Pedido
  } else {
    selectedPedido.value = null
    pedidoSearch.value = ''
  }
  modalError.value = null
  showModal.value = true
  loadPedidoCache()
}

function fecharModal() {
  showModal.value = false
  editandoRastreamento.value = null
  modalError.value = null
  selectedPedido.value = null
  pedidoSearch.value = ''
}

function formatarCodigo(event: Event) {
  const input = event.target as HTMLInputElement
  let valor = input.value.toUpperCase().replace(/[^A-Z0-9]/g, '')
  
  // Limitar a 13 caracteres (formato padrão dos Correios)
  if (valor.length > 13) {
    valor = valor.substring(0, 13)
  }
  
  formData.value.codigo_rastreio = valor
  input.value = valor
}

async function consultarESalvar() {
  if (!formData.value.codigo_rastreio) return
  
  try {
    salvando.value = true
    modalError.value = null
    
    await rastreamentoStore.consultarESalvarRastreamento({
      codigo: formData.value.codigo_rastreio,
      servico_id: '0001'
    })
    
    await carregarDados()
    fecharModal()
  } catch (error: any) {
    modalError.value = error.message || 'Erro ao consultar e salvar rastreamento'
  } finally {
    salvando.value = false
  }
}

async function salvarRastreamento() {
  if (!formData.value.codigo_rastreio) return

  try {
    salvando.value = true
    modalError.value = null

    if (editandoRastreamento.value) {
      await rastreamentoStore.atualizarRastreamento(
        editandoRastreamento.value.id,
        formData.value
      )
    } else {
      // Create then immediately fetch real data from Wonca API
      const novo = await rastreamentoStore.criarRastreamento(formData.value)
      if (novo?.id) {
        atualizarOnline(novo).catch(() => {})
      }
    }

    await carregarDados()
    fecharModal()
  } catch (error: any) {
    modalError.value = error.message || 'Erro ao salvar rastreamento'
  } finally {
    salvando.value = false
  }
}

async function removerRastreamento(rastreamento: Rastreamento) {
  if (!confirm(`Tem certeza que deseja remover o rastreamento ${rastreamento.codigo_rastreio}?`)) {
    return
  }
  
  try {
    await rastreamentoStore.removerRastreamento(rastreamento.id)
    await carregarDados()
  } catch (error: any) {
    console.error('Erro ao remover rastreamento:', error)
  }
}

function getStatusClass(status: string): string {
  return rastreamentoStore.getStatusColor(status)
}

function getStatusBadgeClass(status: string): string {
  switch (status) {
    case 'PENDENTE': return 'badge-pendente'
    case 'EM_TRANSITO': return 'badge-em-transito'
    case 'ENTREGUE': return 'badge-entregue'
    case 'ERRO':
    case 'NAO_ENCONTRADO': return 'badge-erro'
    default: return 'badge-pendente'
  }
}

function getStatusText(status: string): string {
  switch (status) {
    case 'PENDENTE': return 'Pendente'
    case 'EM_TRANSITO': return 'Em Trânsito'
    case 'ENTREGUE': return 'Entregue'
    case 'ERRO': return 'Erro'
    case 'NAO_ENCONTRADO': return 'Não encontrado'
    default: return status
  }
}

function formatarData(data: string): string {
  return rastreamentoStore.formatarData(data)
}

function getStatusCardClass(status: string): string {
  switch (status) {
    case 'ENTREGUE':
      return 'card-status-entregue'
    case 'EM_TRANSITO':
      return 'card-status-transito'
    case 'PENDENTE':
      return 'card-status-pendente'
    case 'ERRO':
    case 'NAO_ENCONTRADO':
      return 'card-status-erro'
    default:
      return 'card-status-default'
  }
}

// Novas funções para a lista
async function copiarCodigo(rastreamento: Rastreamento) {
  try {
    await navigator.clipboard.writeText(rastreamento.codigo_rastreio)
    triggerFlash(rastreamento.id)
  } catch (error) {
    console.error('Erro ao copiar código:', error)
  }
}


// Funções para controlar expansão dos cards
function toggleCard(cardId: string) {
  if (expandedCards.value.has(cardId)) {
    expandedCards.value.delete(cardId)
  } else {
    expandedCards.value.add(cardId)
  }
}

function isCardExpanded(cardId: string): boolean {
  return expandedCards.value.has(cardId)
}

function formatEventDate(dateStr: string): string {
  if (!dateStr) return ''
  try {
    // Handle "2026-04-30 16:51:46.000000" format from Correios via Wonca
    const d = new Date(dateStr.replace(' ', 'T').split('.')[0])
    if (isNaN(d.getTime())) return dateStr
    return d.toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateStr
  }
}

async function atualizarOnline(rastreamento: Rastreamento) {
  const s = new Set(refreshingIds.value)
  s.add(rastreamento.id)
  refreshingIds.value = s
  try {
    await rastreamentoStore.atualizarOnline(rastreamento.id)
    // The store already updates the item in-place via splice — no full reload needed
    // Refresh resumo stats silently in background
    rastreamentoStore.obterResumoDashboard().then(v => { resumo.value = rastreamentoStore.resumoDashboard }).catch(() => {})
    triggerFlash(rastreamento.id)
  } catch (err: any) {
    console.error('Erro ao atualizar rastreamento:', err)
  } finally {
    const s2 = new Set(refreshingIds.value)
    s2.delete(rastreamento.id)
    refreshingIds.value = s2
  }
}

function isRefreshing(id: string): boolean {
  return refreshingIds.value.has(id)
}

function trackingProgressStep(rastreamento: Rastreamento): number {
  if (rastreamento.status === 'ENTREGUE') return 4
  if (rastreamento.status === 'ERRO' || rastreamento.status === 'NAO_ENCONTRADO') return 0
  const latest = (rastreamento.historico_eventos?.[0]?.situacao || '').toLowerCase()
  if (latest.includes('saiu para entrega') || latest.includes('veículo de entrega')) return 3
  if (rastreamento.status === 'EM_TRANSITO') return 2
  return 1
}

// Lifecycle
onMounted(async () => {
  await carregarDados()
  // Pré-filtrar se veio com ?search= na URL (ex: clique no badge de pedido)
  if (route.query.search) {
    filtros.value.busca = String(route.query.search)
  }
})
</script>

<style scoped>
.rastreamento-page {
  min-height: 100vh;
  background-color: #f9fafb;
}

/* Header */
.page-header {
  background-color: white;
  border-bottom: 1px solid #e5e7eb;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
}

.header-content {
  padding: 1.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.back-button {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 0.5rem;
  background-color: #f3f4f6;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  transition: all 0.2s;
}

.back-button:hover {
  background-color: #e5e7eb;
  color: #374151;
}

.back-button svg {
  width: 1.25rem;
  height: 1.25rem;
}

.page-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: #111827;
}

.page-subtitle {
  margin: 0;
  font-size: 0.875rem;
  color: #6b7280;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

/* Stats Section */
.stats-section {
  padding: 0.75rem 1.5rem 0.5rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.5rem;
  max-width: 100%;
}

.stat-card {
  background-color: white;
  border-radius: 0.5rem;
  padding: 0.5rem 0.6rem;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.08);
  border: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.stat-icon {
  width: 1.5rem;
  height: 1.5rem;
  border-radius: 0.35rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon svg {
  width: 0.7rem;
  height: 0.7rem;
}

.stat-icon.blue {
  background-color: #dbeafe;
  color: #2563eb;
}

.stat-icon.yellow {
  background-color: #fef3c7;
  color: #d97706;
}

.stat-icon.green {
  background-color: #dcfce7;
  color: #16a34a;
}

.stat-icon.red {
  background-color: #fecaca;
  color: #dc2626;
}

.stat-label {
  margin: 0 0 0.1rem 0;
  font-size: 0.65rem;
  font-weight: 500;
  color: #6b7280;
  white-space: nowrap;
}

.stat-value {
  margin: 0;
  font-size: 0.875rem;
  font-weight: 700;
  color: #111827;
  line-height: 1;
}

/* Filters */
.filters-section {
  padding: 0 1.5rem 1.5rem;
}

.filters-content {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.search-box {
  flex: 1;
  position: relative;
}

.search-icon {
  position: absolute;
  left: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  width: 1.25rem;
  height: 1.25rem;
  color: #9ca3af;
}

.search-input {
  width: 100%;
  padding: 0.75rem 0.75rem 0.75rem 2.5rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  background-color: white;
}

.search-input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.status-select {
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  background-color: white;
  min-width: 150px;
}

.status-select:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

/* Loading */
.loading-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  color: #6b7280;
}

.loading-spinner {
  margin-bottom: 1rem;
}

.spinner {
  width: 2rem;
  height: 2rem;
  animation: spin 1s linear infinite;
}

.spinner-track {
  opacity: 0.25;
}

.spinner-path {
  opacity: 0.75;
}

/* Rastreamentos Grid */
.rastreamentos-section {
  padding: 0 1.5rem 2rem;
}

@media (max-width: 768px) {
  .rastreamentos-section {
    padding: 0 0.5rem 1rem;
  }
}

.empty-state {
  text-align: center;
  padding: 3rem;
  color: #6b7280;
}

.empty-icon {
  width: 4rem;
  height: 4rem;
  margin: 0 auto 1rem;
  color: #9ca3af;
}

.empty-state h3 {
  margin: 0 0 0.5rem 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: #374151;
}

.empty-state p {
  margin: 0 0 1.5rem 0;
}

.rastreamentos-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 1.5rem;
}

.rastreamento-card {
  background-color: white;
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
  overflow: hidden;
  transition: all 0.2s;
}

.rastreamento-card:hover {
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  transform: translateY(-1px);
}

.card-header {
  padding: 1rem;
  border-bottom: 1px solid #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.codigo-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.codigo {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #111827;
  font-family: monospace;
}

.status-badge {
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.25rem 0.5rem;
  border-radius: 0.375rem;
  white-space: nowrap;
}

.card-actions {
  display: flex;
  gap: 0.5rem;
}

.action-btn {
  width: 2rem;
  height: 2rem;
  border-radius: 0.375rem;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f3f4f6;
  color: #6b7280;
  transition: all 0.2s;
}

.action-btn:hover {
  background-color: #e5e7eb;
  color: #374151;
}

.action-btn.delete:hover {
  background-color: #fecaca;
  color: #dc2626;
}

.action-btn svg {
  width: 1rem;
  height: 1rem;
}

.card-content {
  padding: 1rem;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.info-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: #6b7280;
}

.info-value {
  font-size: 0.875rem;
  color: #111827;
}

/* Eventos */
.eventos-section {
  border-top: 1px solid #f3f4f6;
  padding-top: 1rem;
}

.eventos-title {
  margin: 0 0 0.75rem 0;
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
}

.eventos-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.evento-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
}

.evento-dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  background-color: #2563eb;
  margin-top: 0.375rem;
  flex-shrink: 0;
}

.evento-content {
  flex: 1;
}

.evento-situacao {
  margin: 0 0 0.25rem 0;
  font-size: 0.875rem;
  font-weight: 500;
  color: #111827;
}

.evento-detalhes {
  margin: 0 0 0.25rem 0;
  font-size: 0.75rem;
  color: #6b7280;
}

.evento-data {
  margin: 0;
  font-size: 0.75rem;
  color: #9ca3af;
}

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  text-decoration: none;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-icon {
  width: 1rem;
  height: 1rem;
}

.btn-primary {
  background-color: #2563eb;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: #1d4ed8;
}

.btn-secondary {
  background-color: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
}

.btn-secondary:hover:not(:disabled) {
  background-color: #e5e7eb;
}

.btn-success {
  background-color: #16a34a;
  color: white;
}

.btn-success:hover:not(:disabled) {
  background-color: #15803d;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
  box-sizing: border-box;
}

.modal-content {
  background-color: white;
  border-radius: 0.75rem;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  max-height: 90dvh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e5e7eb;
}

.modal-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #111827;
}

.modal-close {
  width: 2rem;
  height: 2rem;
  border-radius: 0.375rem;
  background: none;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  transition: all 0.2s;
}

.modal-close:hover {
  background-color: #f3f4f6;
  color: #374151;
}

.modal-close svg {
  width: 1.25rem;
  height: 1.25rem;
}

.modal-body {
  padding: 1.5rem;
  flex: 1;
  overflow-y: auto;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1.5rem;
  border-top: 1px solid #e5e7eb;
  background-color: #f9fafb;
}

/* Form */
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-group.full-width {
  grid-column: 1 / -1;
}

.form-group label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
}

.form-input {
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  transition: border-color 0.2s;
}

.form-input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.codigo-input {
  font-family: monospace;
  font-weight: 600;
  text-transform: uppercase;
}

.input-hint {
  font-size: 0.75rem;
  color: #6b7280;
}

.alert {
  padding: 0.75rem;
  border-radius: 0.5rem;
  margin-bottom: 1rem;
  font-size: 0.875rem;
}

.alert-error {
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
}

/* Status Colors */
.text-yellow-600.bg-yellow-100 {
  background-color: #fef3c7;
  color: #92400e;
}

.text-blue-600.bg-blue-100 {
  background-color: #dbeafe;
  color: #1e40af;
}

.text-green-600.bg-green-100 {
  background-color: #dcfce7;
  color: #166534;
}

.text-red-600.bg-red-100 {
  background-color: #fecaca;
  color: #991b1b;
}

.text-gray-600.bg-gray-100 {
  background-color: #f3f4f6;
  color: #4b5563;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* Desktop styles */
.mobile-dropdown-card {
  display: none;
}

/* Responsive */
@media (max-width: 1100px) {
  .mobile-dropdown-card {
    display: block !important;
  }

  .desktop-header,
  .desktop-only {
    display: none !important;
  }


  /* Mobile — cards com borda esquerda de acento por status */
  .mobile-dropdown-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-left-width: 3px;
    border-left-color: #d1d5db;
    border-radius: 0.5rem;
    margin: 0 0 3px 0;
    overflow: hidden;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    transition: border-color 0.15s, box-shadow 0.15s;
    width: 100%;
  }

  .mobile-dropdown-card:hover {
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
  }

  /* Cabeçalho compacto */
  .mobile-card-header {
    display: flex;
    flex-direction: column;
    padding: 6px 9px 5px;
    cursor: pointer;
    transition: background 0.15s;
    gap: 3px;
  }

  .mobile-card-header:hover {
    background: rgba(0,0,0,0.015);
  }

  /* Linha 1: nome + badge + chevron */
  .mch-top {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .mch-name-wrap {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .mch-name {
    font-size: 11px;
    font-weight: 700;
    color: #1e293b;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.2;
  }

  .mch-pedido-badge {
    display: inline-block;
    width: fit-content;
    font-size: 0.58rem;
    font-weight: 700;
    background: #dbeafe;
    color: #1d4ed8;
    padding: 0.08rem 0.38rem;
    border-radius: 4px;
    letter-spacing: 0.03em;
    line-height: 1.4;
  }

  .mch-pedido-btn {
    border: none;
    cursor: pointer;
    transition: background 0.15s;
  }
  .mch-pedido-btn:hover {
    background: #bfdbfe;
  }

  .mch-badge {
    font-size: 7px !important;
    padding: 0.1rem 0.38rem !important;
    flex-shrink: 0;
  }

  /* Linha 2: código + serviço + copiar */
  .mch-code-row {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .mch-service {
    font-size: 7.5px;
    font-weight: 700;
    background: #e0e7ff;
    color: #3730a3;
    padding: 1px 4px;
    border-radius: 99px;
    white-space: nowrap;
    flex-shrink: 0;
  }

  /* Linha 3: descrição */
  .mch-desc {
    margin: 0;
    font-size: 9px;
    color: #94a3b8;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-style: italic;
    line-height: 1.2;
  }

  /* Barra de progresso sutil */
  .mch-progress {
    height: 2px;
    background: rgba(0,0,0,0.07);
    border-radius: 1px;
    margin-top: 4px;
    overflow: hidden;
  }

  .mch-progress-fill {
    height: 100%;
    border-radius: 1px;
    transition: width 0.6s ease;
    min-width: 4px;
  }

  .mpf-em-transito { background: #3b82f6; }
  .mpf-entregue    { background: #10b981; }
  .mpf-pendente    { background: #f59e0b; }
  .mpf-erro, .mpf-nao-encontrado { background: #ef4444; }

  .mobile-header-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
  }

  .mobile-name-section {
    flex: 1;
    min-width: 0;
  }

  .mobile-name {
    font-size: 11px;
    font-weight: 600;
    color: #1e293b;
    line-height: 1.2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .mobile-header-main {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
  }

  .mobile-code-section {
    display: flex;
    align-items: center;
    gap: 4px;
    flex: 1;
    min-width: 0;
  }

  .mobile-code {
    font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
    font-size: 10px;
    font-weight: 600;
    color: #1e293b;
    background: white;
    padding: 3px 6px;
    border-radius: 4px;
    border: 1px solid #cbd5e1;
    letter-spacing: 0.3px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 140px;
  }

  .mobile-copy-btn {
    width: 20px;
    height: 20px;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    background: white;
    color: #64748b;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .mobile-copy-btn svg { width: 10px; height: 10px; }

  .mobile-copy-btn:hover {
    background: #f1f5f9;
    color: #475569;
  }

  .mobile-expand-icon {
    color: #94a3b8;
    flex-shrink: 0;
  }

  .mobile-expand-icon svg {
    width: 14px;
    height: 14px;
    transition: transform 0.25s ease;
  }

  .mobile-expand-icon svg.rotate-180 {
    transform: rotate(180deg);
  }

  /* Conteúdo expansível */
  .mobile-card-content {
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.3s ease, opacity 0.2s ease;
    opacity: 0;
  }

  .mobile-card-content.expanded {
    max-height: 900px;
    opacity: 1;
  }

  .mobile-card-inner {
    padding: 8px 10px;
    background: white;
    border-top: 1px solid #f1f5f9;
  }

  .mobile-content-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 4px 0;
    border-bottom: 1px solid #f8fafc;
  }

  .mobile-content-row:last-child {
    border-bottom: none;
  }

  .mobile-content-label {
    font-size: 10px;
    font-weight: 500;
    color: #94a3b8;
    min-width: 64px;
    flex-shrink: 0;
  }

  .mobile-content-value {
    font-size: 10px;
    font-weight: 500;
    color: #1e293b;
    text-align: right;
    max-width: 62%;
    word-break: break-word;
  }

  .mobile-date-value {
    color: #94a3b8;
    font-size: 9px;
    font-weight: 400;
  }

  .mobile-status-select-expanded {
    padding: 4px 8px;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    background: white;
    min-width: 80px;
    cursor: pointer;
  }

  .mobile-status-select-expanded:focus {
    outline: none;
    border-color: #0445ae;
  }

  .mobile-status-select-expanded.text-yellow-600 { background-color: #f59e0b !important; color: white !important; border-color: #d97706 !important; }
  .mobile-status-select-expanded.text-blue-600   { background-color: #0445ae !important; color: white !important; border-color: #2563eb !important; }
  .mobile-status-select-expanded.text-green-600  { background-color: #10b981 !important; color: white !important; border-color: #059669 !important; }
  .mobile-status-select-expanded.text-red-600    { background-color: #ef4444 !important; color: white !important; border-color: #dc2626 !important; }

  .mobile-content-actions {
    display: flex;
    gap: 5px;
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid #f1f5f9;
  }

  .mobile-action-btn-expanded {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 6px 4px;
    border: 1px solid #e2e8f0;
    border-radius: 5px;
    font-size: 10px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
    background: white;
  }

  .mobile-action-btn-expanded svg { width: 12px; height: 12px; }

  .mobile-action-btn-expanded.edit { color: #475569; }
  .mobile-action-btn-expanded.edit:hover { background: #f1f5f9; border-color: #94a3b8; }

  .mobile-action-btn-expanded.delete { color: #dc2626; border-color: #fca5a5; }
  .mobile-action-btn-expanded.delete:hover { background: #fef2f2; border-color: #f87171; }
  
  .header-content {
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }

  .header-left {
    flex: 1;
  }

  .header-actions {
    justify-content: flex-end;
    flex-shrink: 0;
  }

  .stats-grid {
    grid-template-columns: repeat(4, 1fr);
    gap: 0.25rem;
  }

  .stat-card {
    padding: 0.35rem 0.3rem;
    gap: 0.2rem;
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .stat-icon {
    width: 1.1rem;
    height: 1.1rem;
  }

  .stat-icon svg {
    width: 0.55rem;
    height: 0.55rem;
  }

  .stat-label {
    font-size: 0.55rem;
  }

  .stat-value {
    font-size: 0.75rem;
  }

  .filters-content {
    flex-direction: column;
    align-items: stretch;
  }

  .rastreamentos-grid {
    grid-template-columns: 1fr;
  }

  .info-grid {
    grid-template-columns: 1fr;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .modal-overlay {
    padding: 0.5rem;
    align-items: center;
  }

  .modal-content {
    margin: 0;
    max-height: calc(100vh - 1rem);
    max-height: calc(100dvh - 1rem);
    border-radius: 0.5rem;
  }

  .modal-header {
    padding: 0.875rem 1rem;
  }

  .modal-header h2 {
    font-size: 1.05rem;
  }

  .modal-body {
    padding: 0.875rem 1rem;
  }

  .modal-footer {
    padding: 0.75rem 1rem;
  }

  .rastreamentos-list {
    display: block;
    padding: 0rem;
  }

  .list-header {
    display: none;
  }


  /* Layout mobile: Código e botão na primeira linha */
  .row-codigo {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid #f3f4f6;
  }

  .row-codigo .codigo-text {
    font-size: 0.875rem;
    font-weight: 600;
    font-family: monospace;
  }

  .row-codigo .copy-btn {
    margin-left: 0.5rem;
  }





  /* Esconder campos desktop no mobile */
  .row-destinatario,
  .row-descricao,
  .row-rastreio,
  .row-status,
  .row-data,
  .row-actions {
    display: none !important;
  }

}

/* Estilos da Lista */
.rastreamentos-list {
  padding: 0rem 2rem;
}

.list-header {
  display: grid;
  grid-template-columns: 1fr 1fr 1.5fr 120px 120px 100px 120px;
  gap: 1rem;
  padding: 1rem;
  background-color: #f8fafc;
  border-radius: 0.5rem;
  margin-bottom: 0.5rem;
  font-weight: 600;
  font-size: 0.875rem;
  color: #374151;
  border: 1px solid #e2e8f0;
  align-items: center;
}

.list-header > div {
  display: flex;
  align-items: center;
}

.header-rastreio {
  justify-content: center;
}

.header-status {
  justify-content: center;
}

.header-data {
  justify-content: center;
}

.header-actions {
  justify-content: center;
}

/* Desktop: mostrar apenas rastreamento-row, ocultar dropdown - SEM CORES */
.rastreamento-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1.5fr 120px 120px 100px 120px;
  gap: 1rem;
  padding: 1rem;
  background-color: white !important; /* Sempre branco no desktop */
  border: 1px solid #e5e7eb !important; /* Sempre borda cinza no desktop */
  border-radius: 0.5rem;
  margin-bottom: 0.25rem;
  align-items: center;
  transition: all 0.2s;
}

.rastreamento-row:hover {
  border-color: #cbd5e1 !important; /* Hover cinza no desktop */
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
}

/* Desktop: Forçar selects sem cores de status */
.rastreamento-row .status-select-inline {
  background-color: white !important;
  color: #374151 !important;
  border-color: #d1d5db !important;
}

/* Desktop: Garantir que classes mobile de status não afetem o desktop */
@media (min-width: 1101px) {
  .mobile-rastreamento-row-status-entregue,
  .mobile-rastreamento-row-status-em-transito,
  .mobile-rastreamento-row-status-pendente,
  .mobile-rastreamento-row-status-erro,
  .mobile-rastreamento-row-status-nao-encontrado {
    background-color: transparent !important;
    border: none !important;
  }
}

/* Ocultar dropdown cards no desktop */
.mobile-dropdown-card {
  display: none;
  background-color: transparent;
  border: none;
}

/* Acento lateral colorido por status — apenas no mobile */
@media (max-width: 1100px) {
  /* Outer row: sem fundo/borda própria */
  .mobile-rastreamento-row-status-entregue,
  .mobile-rastreamento-row-status-em-transito,
  .mobile-rastreamento-row-status-pendente,
  .mobile-rastreamento-row-status-erro,
  .mobile-rastreamento-row-status-nao-encontrado {
    background-color: transparent !important;
    border: none !important;
    border-radius: 0;
    margin-bottom: 0;
  }

  /* A cor aparece como acento lateral no card filho */
  .mobile-rastreamento-row-status-entregue .mobile-dropdown-card {
    border-left-color: #10b981;
    background: #f5fdf8;
  }

  .mobile-rastreamento-row-status-em-transito .mobile-dropdown-card {
    border-left-color: #3b82f6;
    background: #f8fbff;
  }

  .mobile-rastreamento-row-status-pendente .mobile-dropdown-card {
    border-left-color: #f59e0b;
    background: #fffdf5;
  }

  .mobile-rastreamento-row-status-erro .mobile-dropdown-card,
  .mobile-rastreamento-row-status-nao-encontrado .mobile-dropdown-card {
    border-left-color: #ef4444;
    background: #fff8f8;
  }
}

/* Mobile pequeno: leve compactação adicional */
@media (max-width: 768px) {
  .mobile-card-header { padding: 5px 8px 4px; }
  .mch-name { font-size: 10.5px; }
  .mobile-code { font-size: 9px; max-width: 130px; padding: 2px 5px; }
  .mobile-card-inner { padding: 7px 9px; }
  .mobile-content-label { font-size: 9.5px; }
  .mobile-content-value { font-size: 9.5px; }
  .mobile-copy-btn { width: 18px; height: 18px; }
}

.row-codigo {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.codigo-text {
  font-family: monospace;
  font-weight: 600;
  font-size: 0.875rem;
  color: #111827;
}

.copy-btn {
  width: 1.5rem;
  height: 1.5rem;
  border: none;
  background: #f3f4f6;
  border-radius: 0.25rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  transition: all 0.2s;
}

.copy-btn:hover {
  background: #e5e7eb;
  color: #374151;
}

.row-destinatario {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
  overflow: hidden;
}
.row-dest-name {
  font-size: 0.875rem;
  color: #111827;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.row-descricao {
  font-size: 0.875rem;
  color: #111827;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.row-status {
  display: flex;
  align-items: center;
}

.status-select-inline {
  width: 100%;
  padding: 0.375rem 0.5rem;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.status-select-inline:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
}

/* Status colors for select */
.status-select-inline.text-yellow-600 {
  background-color: #f59e0b !important;
  color: white !important;
  border-color: #d97706 !important;
}

.status-select-inline.text-blue-600 {
  background-color: #0445ae !important;
  color: white !important;
  border-color: #2563eb !important;
}

.status-select-inline.text-green-600 {
  background-color: #10b981 !important;
  color: white !important;
  border-color: #059669 !important;
}

.status-select-inline.text-red-600 {
  background-color: #ef4444 !important;
  color: white !important;
  border-color: #dc2626 !important;
}

.row-data {
  font-size: 0.75rem;
  color: #6b7280;
  text-align: center;
}

.row-actions {
  display: flex;
  gap: 0.25rem;
  justify-content: center;
}

.action-btn {
  width: 1.75rem;
  height: 1.75rem;
  border: none;
  background: #f3f4f6;
  border-radius: 0.25rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  transition: all 0.2s;
}

.action-btn:hover {
  background: #e5e7eb;
  color: #374151;
}

.action-btn.delete:hover {
  background: #fecaca;
  color: #dc2626;
}

.row-rastreio {
  display: flex;
  justify-content: center;
}

.rastreio-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  background: linear-gradient(135deg, #fbbf24 0%, #fbff00 100%);
  color: #1f2937;
  border: none;
  border-radius: 0.375rem;
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  text-decoration: none;
  border: 1px solid #f59e0b;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
}

.rastreio-btn:hover {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  transform: translateY(-1px);
  box-shadow: 0 4px 8px 0 rgba(245, 158, 11, 0.3);
  border-color: #d97706;
}

.rastreio-btn svg {
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
}

/* Quebra a linha da listagem para 1 coluna e empilha os campos */
@media (max-width: 1100px) {
  .rastreamentos-list .list-header {
    display: none !important; /* some o cabeçalho em telas menores */
  }


  /* Cada célula passa a ocupar a linha inteira, abaixo do bloco de código */
  .row-destinatario,
  .row-descricao,
  .row-rastreio,
  .row-status,
  .row-data,
  .row-actions {
    grid-column: 1 / -1 !important;
    justify-content: flex-start; /* evita centralização estranha herdada */
  }
}


/* Mobile: empilha e garante que o conteúdo quebre corretamente */
@media (max-width: 768px) {
  .mobile-main-row {
    display: grid !important;
    grid-template-columns: 1fr !important;
    align-items: stretch;
  }


  /* As linhas de info podem quebrar para a próxima linha */
  .mobile-info-row {
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
  }

  /* O valor deve poder ocupar a linha inteira sem cortar */
  .mobile-value {
    max-width: 100%;
    word-break: break-word;
    overflow-wrap: anywhere;
  }

  /* O select de status não deve estourar a largura */
  .mobile-status-select {
    width: 100%;
    max-width: 260px;           /* ajuste fino opcional */
  }

  .mobile-rastreio-section,
  .row-rastreio {
    width: 100%;
    display: flex;
    justify-content: center; /* ou flex-start se quiser alinhado à esquerda */
    margin-top: 0.5rem;
  }

  .mobile-rastreio-btn-header,
  .rastreio-btn {
    width: 100%;        /* ocupa a linha toda */
    max-width: 100%;    /* evita estourar */
    justify-content: center;
    box-sizing: border-box;
  }
  
}

/* ===== Ajustes de TAMANHO: somente MOBILE ===== */
@media (max-width: 768px) {
  /* Header mais compacto */
  .page-header { border-bottom-width: 0; }
  .header-content {
    padding: 0.75rem 1rem;
    gap: 0.5rem;
  }
  .back-button {
    width: 2rem; height: 2rem; border-radius: 0.4rem;
  }
  .back-button svg { width: 1rem; height: 1rem; }

  .page-title {
    font-size: 1.125rem; /* antes 1.5rem */
    line-height: 1.2;
  }
  .page-subtitle {
    font-size: 0.75rem;   /* menor */
    color: #6b7280;
  }

  /* Botão "Novo Rastreamento" menor e no canto direito */
  .header-actions {
    justify-content: flex-end;
  }
  
  .header-actions .btn.btn-primary {
    padding: 0.4rem 0.75rem;
    font-size: 0.8rem;
    border-radius: 0.5rem;
    gap: 0.3rem;
    min-width: auto;
  }
  .header-actions .btn.btn-primary .btn-icon {
    width: 0.8rem; height: 0.8rem;
  }

  /* Cards de estatísticas compactos 1×4 */
  .stats-section { padding: 0.5rem 0.125rem 0.25rem; }
  .stats-grid {
    grid-template-columns: repeat(4, 1fr);
    gap: 0.2rem;
    max-width: none;
    width: 100%;
  }
  .stat-card {
    padding: 0.4rem 0.25rem;
    border-radius: 0.4rem;
    gap: 0.15rem;
    margin: 0;
    width: 100%;
    box-sizing: border-box;
    flex-direction: column;
    align-items: center;
    text-align: center;
  }
  .stat-icon {
    width: 1rem; height: 1rem; border-radius: 0.25rem;
  }
  .stat-icon svg { width: 0.5rem; height: 0.5rem; }
  .stat-label { font-size: 0.5rem; margin-bottom: 0; font-weight: 500; white-space: nowrap; }
  .stat-value { font-size: 0.8rem; font-weight: 700; line-height: 1; }

  /* Filtros/Busca com exata largura dos cards */
  .filters-section { padding: 0 0.125rem 0.75rem; }
  .search-input {
    padding: 0.6rem 0.6rem 0.6rem 2.1rem;
    font-size: 0.85rem;
    border-radius: 0.5rem;
    width: 100%;
    margin: 0;
  }
  .search-icon { left: 0.6rem; }

  .status-select {
    padding: 0.6rem;
    font-size: 0.85rem;
    min-width: 0;
    width: 100%;
    margin: 0;
  }
  
  .search-box {
    width: 100%;
    margin: 0;
  }
  
  .filter-select {
    width: 100%;
    margin: 0;
  }

  /* Mobile: ocultar rastreamento-row, mostrar dropdown */
  .rastreamento-row {
    display: none !important;
  }
  
  .mobile-dropdown-card {
    display: block !important;
  }

  /* Lista: largura total, sem padding lateral — cards colam nas bordas */
  .rastreamentos-list {
    padding: 0;
  }

  /* Cabeçalho do card (código + botão Correios) menor */
  .mobile-main-row {
    padding: 0.85rem 0.9rem;
    border-radius: 0.75rem 0.75rem 0 0;
  }
  .mobile-codigo-section .codigo-text {
    padding: 0.5rem 0.75rem;
    font-size: 0.95rem;
  }
  .mobile-codigo-section .copy-btn {
    width: 2.1rem; height: 2.1rem; border-radius: 0.45rem;
  }
  .mobile-rastreio-btn-header {
    padding: 0.55rem 0.75rem;
    font-size: 0.85rem;
    min-width: 100px;
    border-radius: 0.6rem;
  }

  /* Blocos de info mais justos */
  .mobile-info-section { padding: 0.75rem 0.9rem; }
  .mobile-info-row {
    padding: 0.6rem 0.7rem;
    margin-bottom: 0.6rem;
    border-radius: 0.5rem;
  }
  .mobile-label {
    font-size: 0.75rem;
    min-width: 80px;
  }
  .mobile-value {
    font-size: 0.9rem;
  }
  .mobile-status-select {
    padding: 0.75rem;
    font-size: 0.85rem;
    max-width: 220px;
    border-radius: 0.5rem;
  }
  .mobile-date { font-size: 0.75rem; }

  /* Ações do card mais compactas */
  .mobile-actions {
    padding: 1rem;
    margin-top: 0.75rem;
    gap: 0.75rem;
    border-top-width: 1px;
  }
  .mobile-action-btn {
    padding: 0.75rem 1rem;
    font-size: 0.85rem;
    min-height: 42px;
    border-radius: 0.6rem;
    max-width: 120px;
  }
}

@media (max-width: 380px) {
  .page-title { font-size: 1rem; }
  .header-actions .btn.btn-primary { font-size: 0.8rem; padding: 0.45rem 0.7rem; }
  .stat-value { font-size: 0.7rem; }
  .stat-label { font-size: 0.45rem; }
  .stat-icon { width: 0.875rem; height: 0.875rem; }
  .stat-icon svg { width: 0.45rem; height: 0.45rem; }
}

/* ── Freight Calculator (fixed section) ─────────────────────────────────────── */
.freight-section {
  padding: 0 1.5rem 0.75rem;
}
.freight-inner {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 0.75rem 1rem;
  box-shadow: 0 1px 2px rgba(0,0,0,0.06);
}
.freight-title-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 0.6rem;
  color: #374151;
}
.freight-title {
  font-size: 0.8rem;
  font-weight: 600;
  color: #374151;
}
.freight-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: flex-end;
}
.freight-field {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  flex: 1;
  min-width: 100px;
}
.freight-field-sm { max-width: 80px; flex: none; }
.freight-label { font-size: 0.7rem; font-weight: 500; color: #374151; }
.freight-input {
  padding: 0.4rem 0.5rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 0.8rem;
  background: white;
  width: 100%;
  box-sizing: border-box;
}
.freight-input:focus { outline: none; border-color: #2563eb; box-shadow: 0 0 0 2px rgba(37,99,235,0.1); }
.freight-cep-origem-row {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}
.freight-cep-locked {
  font-size: 0.85rem;
  font-weight: 600;
  color: #111827;
  letter-spacing: 0.05em;
  font-family: monospace;
  padding: 0.3rem 0;
}
.freight-cep-edit-btn {
  background: none;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  padding: 0.25rem 0.4rem;
  cursor: pointer;
  color: #6b7280;
  display: flex;
  align-items: center;
  transition: all 0.15s;
  flex-shrink: 0;
}
.freight-cep-edit-btn:hover { background: #f3f4f6; color: #374151; }
.freight-cep-save-btn {
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 0.25rem 0.5rem;
  font-size: 0.72rem;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.15s;
}
.freight-cep-save-btn:hover { background: #1d4ed8; }
.freight-calc-btn {
  padding: 0.4rem 0.9rem;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  align-self: flex-end;
  transition: background 0.15s;
}
.freight-calc-btn:hover:not(:disabled) { background: #1d4ed8; }
.freight-calc-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.freight-erro { font-size: 0.75rem; color: #dc2626; margin-top: 0.4rem; }
.freight-resultados {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.6rem;
  flex-wrap: wrap;
}
.freight-resultado-item {
  flex: 1;
  min-width: 110px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0.5rem 0.65rem;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  transition: border-color 0.15s;
}
.freight-resultado-item.freight-resultado-selected {
  border-color: #2563eb;
  background: #eff6ff;
}
.freight-resultado-servico { font-size: 0.7rem; font-weight: 700; color: #1e40af; }
.freight-resultado-valor { font-size: 0.95rem; font-weight: 700; color: #111827; }
.freight-resultado-prazo { font-size: 0.65rem; color: #6b7280; }
.freight-resultado-erro { font-size: 0.65rem; color: #dc2626; }
.freight-usar-btn {
  margin-top: 0.2rem;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 0.2rem 0.45rem;
  font-size: 0.65rem;
  cursor: pointer;
  align-self: flex-start;
  transition: background 0.15s;
}
.freight-usar-btn:hover { background: #1d4ed8; }
.freight-selected-hint {
  margin-top: 0.5rem;
  font-size: 0.72rem;
  color: #1e40af;
  background: #eff6ff;
  border-radius: 6px;
  padding: 0.3rem 0.6rem;
}

/* Modal freight apply hint */
.modal-frete-hint { margin-top: 0.35rem; }
.modal-frete-apply-btn {
  background: none;
  border: 1px dashed #2563eb;
  color: #2563eb;
  border-radius: 5px;
  padding: 0.25rem 0.6rem;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
}
.modal-frete-apply-btn:hover { background: #eff6ff; }

@media (max-width: 768px) {
  .freight-section { padding: 0 0.125rem 0.5rem; }
  .freight-inner { padding: 0.6rem 0.75rem; border-radius: 8px; }
  .freight-fields { gap: 0.4rem; }
  .freight-field { min-width: 80px; }
  .freight-field-sm { max-width: 70px; }
}

/* ── Status badges ───────────────────────────────────────────────────────────── */
.status-badge-inline {
  display: inline-block;
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  white-space: nowrap;
  letter-spacing: 0.02em;
}
.badge-pendente { background: #fef3c7; color: #92400e; }
.badge-em-transito { background: #dbeafe; color: #1e40af; }
.badge-entregue { background: #d1fae5; color: #065f46; }
.badge-erro { background: #fee2e2; color: #991b1b; }

/* ── Last event column ───────────────────────────────────────────────────────── */
.row-ultimo-evento { overflow: hidden; }
.ultimo-evento-text {
  font-size: 0.75rem;
  color: #374151;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
  max-width: 180px;
}

/* ── Refresh button ──────────────────────────────────────────────────────────── */
.action-btn.refresh { color: #2563eb; }
.action-btn.refresh:hover { background-color: #eff6ff; color: #1d4ed8; }
.action-btn.refresh:disabled { opacity: 0.5; cursor: not-allowed; }
.mobile-action-btn-expanded.refresh { background-color: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }
.mobile-action-btn-expanded.refresh:disabled { opacity: 0.5; cursor: not-allowed; }

@keyframes spin-btn { to { transform: rotate(360deg); } }
.spin { animation: spin-btn 0.8s linear infinite; }

/* ── Card flash highlight ─────────────────────────────────────────────────────── */
@keyframes card-flash-anim {
  0%   { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); background-color: transparent; }
  25%  { box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.4); background-color: rgba(219, 234, 254, 0.45); }
  70%  { box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15); background-color: rgba(219, 234, 254, 0.15); }
  100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); background-color: transparent; }
}

.card-flash {
  animation: card-flash-anim 1.2s ease-out;
  border-radius: 0.5rem;
}

/* ── Última atualização ───────────────────────────────────────────────────────── */
.row-data {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.row-ultima-att {
  font-size: 0.65rem;
  color: #9ca3af;
  font-style: italic;
}

.ultima-att-value {
  color: #6b7280;
  font-style: italic;
}

/* ── Progress track ──────────────────────────────────────────────────────────── */
.progress-track {
  margin: 0.75rem 0 0.5rem;
  padding: 0.75rem;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}
.progress-track.track-erro { background: #fef2f2; border-color: #fecaca; }
.track-steps {
  display: flex;
  justify-content: space-between;
  position: relative;
  margin-bottom: 0.5rem;
}
.track-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  flex: 1;
  position: relative;
  z-index: 1;
}
.step-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid #d1d5db;
  background: white;
  transition: all 0.2s;
}
.step-dot.dot-done { background: #3b82f6; border-color: #3b82f6; }
.step-dot.dot-active { background: #3b82f6; border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,0.2); }
.step-dot.dot-future { background: white; border-color: #d1d5db; }
.progress-track.track-erro .step-dot { border-color: #ef4444; }
.step-label { font-size: 0.6rem; color: #6b7280; text-align: center; line-height: 1.2; white-space: nowrap; }
.track-bar {
  height: 4px;
  background: #e2e8f0;
  border-radius: 2px;
  overflow: hidden;
  margin: 0 7px;
}
.track-fill {
  height: 100%;
  background: #3b82f6;
  border-radius: 2px;
  transition: width 0.4s ease;
}
.progress-track.track-erro .track-fill { background: #ef4444; }

/* ── Events timeline ─────────────────────────────────────────────────────────── */
.events-timeline {
  margin-top: 0.75rem;
  border-top: 1px solid #e5e7eb;
  padding-top: 0.75rem;
}
.timeline-title {
  font-size: 0.7rem;
  font-weight: 600;
  color: #374151;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin: 0 0 0.5rem;
}
.timeline-list { display: flex; flex-direction: column; gap: 0; }
.timeline-event {
  display: flex;
  gap: 0.6rem;
  position: relative;
  padding-bottom: 0.75rem;
}
.timeline-event:last-child { padding-bottom: 0; }
.timeline-event:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 5px;
  top: 14px;
  bottom: 0;
  width: 2px;
  background: #e5e7eb;
}
.tl-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #d1d5db;
  border: 2px solid #9ca3af;
  flex-shrink: 0;
  margin-top: 2px;
  position: relative;
  z-index: 1;
}
.tl-dot.tl-dot-active { background: #3b82f6; border-color: #3b82f6; }
.tl-content { flex: 1; min-width: 0; }
.tl-situacao { font-size: 0.8rem; font-weight: 500; color: #111827; margin: 0 0 0.1rem; }
.tl-situacao-sub { font-size: 0.72rem; color: #4b5563; margin: 0 0 0.1rem; font-style: italic; }
.tl-meta { font-size: 0.7rem; color: #6b7280; margin: 0 0 0.1rem; }
.tl-local-tipo { color: #9ca3af; }
.tl-destino { font-size: 0.7rem; color: #2563eb; margin: 0 0 0.1rem; font-weight: 500; }
.tl-detalhe { font-size: 0.68rem; color: #9ca3af; margin: 0; }

/* ── Rastreio info bar ───────────────────────────────────────────────────────── */
.rastreio-info-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  margin: 0.5rem 0 0.75rem;
}
.ri-badge {
  font-size: 0.65rem;
  font-weight: 700;
  background: #2563eb;
  color: white;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
.ri-previsao {
  font-size: 0.72rem;
  color: #1e40af;
}
.ri-previsao strong { font-weight: 600; }
.ri-atrasado {
  font-size: 0.65rem;
  font-weight: 600;
  background: #ef4444;
  color: white;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
}

/* ── Desktop last-event column enhancements ─────────────────────────────────── */
.desktop-service-badge {
  display: inline-block;
  font-size: 0.6rem;
  font-weight: 700;
  background: #2563eb;
  color: white;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  margin-bottom: 0.2rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.row-ultimo-evento { flex-direction: column; align-items: flex-start; gap: 0.15rem; }
.desktop-previsao {
  font-size: 0.65rem;
  color: #6b7280;
  margin-top: 0.1rem;
}

/* ── Desktop expanded detail panel ─────────────────────────────────────────── */
.desktop-detail-panel {
  display: none;
  border-top: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 1rem 1.5rem;
  animation: slideDown 0.2s ease;
}
@keyframes slideDown {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
.desktop-detail-body {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 1.5rem;
  align-items: start;
}
.desktop-timeline .timeline-list {
  max-height: 320px;
  overflow-y: auto;
  padding-right: 0.25rem;
}
.desktop-timeline .timeline-list::-webkit-scrollbar { width: 3px; }
.desktop-timeline .timeline-list::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 2px; }

@media (min-width: 769px) {
  .desktop-detail-panel { display: block; }
}
@media (max-width: 768px) {
  .desktop-detail-panel { display: none !important; }
  .desktop-service-badge { display: none; }
  .desktop-previsao { display: none; }
}

/* ── Pedido link badge ────────────────────────────────────────────────────────── */
.pedido-link-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.15rem 0.5rem;
  background: #eff6ff;
  color: #2563eb;
  border-radius: 0.375rem;
  font-size: 0.72rem;
  font-weight: 600;
  margin-right: 0.35rem;
  border: 1px solid #bfdbfe;
  white-space: nowrap;
  width: fit-content;
}
.pedido-link-btn {
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  text-decoration: none;
}
.pedido-link-btn:hover {
  background: #dbeafe;
  color: #1d4ed8;
}

/* ── Pedido autocomplete in rastreamento modal ──────────────────────────────── */
.pedido-suggestion-list {
  position: absolute;
  top: calc(100% + 3px);
  left: 0;
  right: 0;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 6px 18px rgba(0,0,0,.1);
  z-index: 200;
  max-height: 200px;
  overflow-y: auto;
}
.pedido-suggestion-item {
  display: flex;
  flex-direction: column;
  gap: .1rem;
  width: 100%;
  text-align: left;
  padding: .5rem .85rem;
  background: none;
  border: none;
  cursor: pointer;
  border-bottom: 1px solid #f3f4f6;
}
.pedido-suggestion-item:last-child { border-bottom: none; }
.pedido-suggestion-item:hover { background: #f9fafb; }
.sug-num { font-size: .82rem; font-weight: 700; color: #2563eb; }
.sug-info { font-size: .73rem; color: #6b7280; }

</style>