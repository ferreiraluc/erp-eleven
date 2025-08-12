<template>
  <div class="dashboard">
    <!-- Header -->
    <header class="dashboard-header">
      <div class="header-content">
        <div class="header-left">
          <div class="app-logo">
            <svg class="logo-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
          </div>
          <div class="app-info">
            <h1 class="app-title">ERP Eleven</h1>
            <p class="welcome-text">{{ $t('dashboard.welcomeBack', { name: authStore.userName }) }}</p>
          </div>
        </div>
        
        <div class="header-right">
          <div class="header-left-controls">
            <!-- Currency, Language, and Exchange Rates (Mobile only) -->
            <div class="mobile-controls">
              <!-- Currency and Language Selectors -->
              <div class="currency-language-group">
                <!-- Currency Selector -->
                <div class="header-control">
                  <div class="dropdown">
                    <button @click="toggleCurrencyDropdown" class="header-dropdown-button">
                      <span class="control-flag">{{ currencyStore.getCurrentCurrency?.flag }}</span>
                      <span class="control-text">{{ currencyStore.selectedCurrency }}</span>
                      <svg class="dropdown-icon" :class="{ 'rotate': showCurrencyDropdown }" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                    <div v-if="showCurrencyDropdown" class="header-dropdown-menu">
                      <button
                        v-for="currency in currencyStore.availableCurrencies"
                        :key="currency.code"
                        @click="handleCurrencyChange(currency.code)"
                        class="header-dropdown-item"
                        :class="{ 'active': currency.code === currencyStore.selectedCurrency }"
                      >
                        <span class="control-flag">{{ currency.flag }}</span>
                        <div class="currency-info">
                          <span class="currency-code">{{ currency.code }}</span>
                          <span class="currency-name">{{ currency.name }}</span>
                        </div>
                      </button>
                    </div>
                  </div>
                </div>

                <!-- Language Selector -->
                <div class="header-control">
                  <div class="dropdown">
                    <button @click="toggleLanguageDropdown" class="header-dropdown-button">
                      <span class="control-flag">{{ getCurrentLanguage?.flag }}</span>
                      <span class="control-text">{{ getCurrentLanguage?.code?.toUpperCase() }}</span>
                      <svg class="dropdown-icon" :class="{ 'rotate': showLanguageDropdown }" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                    <div v-if="showLanguageDropdown" class="header-dropdown-menu">
                      <button
                        v-for="lang in availableLocales"
                        :key="lang.code"
                        @click="handleLanguageChange(lang.code)"
                        class="header-dropdown-item"
                        :class="{ 'active': lang.code === currentLocale }"
                      >
                        <span class="control-flag">{{ lang.flag }}</span>
                        <span class="language-name">{{ lang.name }}</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
              
              <!-- Exchange Rates Display -->
              <div class="header-control">
                <div class="exchange-rates-header" @click="handleHeaderClick" :class="{ 'editable': canEditRates }" style="cursor: pointer;">
                  <div class="rates-display">
                    <div class="rate-item-header">
                      <span class="rate-flag">🇺🇸→🇵🇾</span>
                      <span class="rate-value-header">{{ typeof exchangeRates['G$'] === 'number' ? exchangeRates['G$'].toFixed(0) : '7500' }}</span>
                    </div>
                    <div class="rate-item-header">
                      <span class="rate-flag">🇺🇸→🇧🇷</span>
                      <span class="rate-value-header">{{ typeof exchangeRates['R$'] === 'number' ? exchangeRates['R$'].toFixed(2) : '5.85' }}</span>
                    </div>
                  </div>
                  <svg v-if="canEditRates" class="edit-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </div>
              </div>
            </div>
          </div>

          <div class="header-right-controls">
            <!-- Currency, Language, and Exchange Rates (Desktop only) -->
            <div class="desktop-controls">
              <!-- Currency and Language Selectors -->
              <div class="currency-language-group">
                <!-- Currency Selector -->
                <div class="header-control">
                  <div class="dropdown">
                    <button @click="toggleCurrencyDropdown" class="header-dropdown-button">
                      <span class="control-flag">{{ currencyStore.getCurrentCurrency?.flag }}</span>
                      <span class="control-text">{{ currencyStore.selectedCurrency }}</span>
                      <svg class="dropdown-icon" :class="{ 'rotate': showCurrencyDropdown }" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                    <div v-if="showCurrencyDropdown" class="header-dropdown-menu">
                      <button
                        v-for="currency in currencyStore.availableCurrencies"
                        :key="currency.code"
                        @click="handleCurrencyChange(currency.code)"
                        class="header-dropdown-item"
                        :class="{ 'active': currency.code === currencyStore.selectedCurrency }"
                      >
                        <span class="control-flag">{{ currency.flag }}</span>
                        <div class="currency-info">
                          <span class="currency-code">{{ currency.code }}</span>
                          <span class="currency-name">{{ currency.name }}</span>
                        </div>
                      </button>
                    </div>
                  </div>
                </div>

                <!-- Language Selector -->
                <div class="header-control">
                  <div class="dropdown">
                    <button @click="toggleLanguageDropdown" class="header-dropdown-button">
                      <span class="control-flag">{{ getCurrentLanguage?.flag }}</span>
                      <span class="control-text">{{ getCurrentLanguage?.code?.toUpperCase() }}</span>
                      <svg class="dropdown-icon" :class="{ 'rotate': showLanguageDropdown }" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                    <div v-if="showLanguageDropdown" class="header-dropdown-menu">
                      <button
                        v-for="lang in availableLocales"
                        :key="lang.code"
                        @click="handleLanguageChange(lang.code)"
                        class="header-dropdown-item"
                        :class="{ 'active': lang.code === currentLocale }"
                      >
                        <span class="control-flag">{{ lang.flag }}</span>
                        <span class="language-name">{{ lang.name }}</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
              
              <!-- Exchange Rates Display -->
              <div class="header-control">
                <div class="exchange-rates-header" @click="handleHeaderClick" :class="{ 'editable': canEditRates }" style="cursor: pointer;">
                  <div class="rates-display">
                    <div class="rate-item-header">
                      <span class="rate-flag">🇺🇸→🇵🇾</span>
                      <span class="rate-value-header">{{ typeof exchangeRates['G$'] === 'number' ? exchangeRates['G$'].toFixed(0) : '7500' }}</span>
                    </div>
                    <div class="rate-item-header">
                      <span class="rate-flag">🇺🇸→🇧🇷</span>
                      <span class="rate-value-header">{{ typeof exchangeRates['R$'] === 'number' ? exchangeRates['R$'].toFixed(2) : '5.85' }}</span>
                    </div>
                  </div>
                  <svg v-if="canEditRates" class="edit-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </div>
              </div>
            </div>

            <div class="current-time">
              <svg class="time-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {{ currentTime }}
            </div>
            
            <div class="divider"></div>
            
            <button @click="handleLogout" class="logout-button">
              <svg class="logout-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              <span>{{ $t('common.logout') }}</span>
            </button>
          </div>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="dashboard-main">
      <!-- Loading State -->
      <div v-if="dashboardStore.isLoading" class="loading-container">
        <div class="loading-content">
          <svg class="loading-spinner" fill="none" viewBox="0 0 24 24">
            <circle class="spinner-track" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="spinner-path" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <p>{{ $t('dashboard.loadingDashboard') }}</p>
        </div>
      </div>

      <!-- Dashboard Content -->
      <div v-else class="dashboard-content">
        <!-- Stats Cards -->
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-content">
              <div class="stat-icon green">
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
                </svg>
              </div>
              <div class="stat-info">
                <p class="stat-label">{{ $t('dashboard.todaysSales') }}</p>
                <p class="stat-value">{{ formatCurrency(dashboardStore.stats?.total_sales_today || 0, 'R$') }}</p>
              </div>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-content">
              <div class="stat-icon blue">
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <div class="stat-info">
                <p class="stat-label">{{ $t('dashboard.weeklySales') }}</p>
                <p class="stat-value">{{ formatCurrency(dashboardStore.stats?.total_sales_week || 0, 'R$') }}</p>
              </div>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-content">
              <div class="stat-icon purple">
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
                </svg>
              </div>
              <div class="stat-info">
                <p class="stat-label">{{ $t('dashboard.pendingOrders') }}</p>
                <p class="stat-value">{{ dashboardStore.stats?.pending_orders || 0 }}</p>
              </div>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-content">
              <div class="stat-icon yellow">
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <div class="stat-info">
                <p class="stat-label">{{ $t('dashboard.activeVendors') }}</p>
                <p class="stat-value">{{ dashboardStore.stats?.active_vendors || 0 }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Quick Actions -->
        <div class="actions-grid">
          <!-- Exchange Rate Card -->
          <div class="action-card exchange-rate-card" @click="navigateToExchangeRates" style="cursor: pointer;">
            <div class="card-header">
              <h3 class="card-title">{{ $t('dashboard.exchangeRate') }}</h3>
              <div class="card-actions">
                <button 
                  v-if="canEditRates"
                  @click.stop="openCardModal"
                  class="edit-rate-btn"
                  style="cursor: pointer;"
                >
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </button>
                <div class="card-icon green">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
                  </svg>
                </div>
                <div class="navigation-arrow">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </div>
            </div>
            <div v-if="isLoadingRates" class="exchange-rate loading">
              <div class="rate-loading">
                <svg class="loading-spinner" fill="none" viewBox="0 0 24 24">
                  <circle class="spinner-track" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="spinner-path" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <p>Carregando taxas...</p>
              </div>
            </div>
            <div v-else class="exchange-rate">
              <div class="rate-grid">
                <div class="rate-item">
                  <span class="rate-label">USD → G$</span>
                  <span class="rate-value">{{ typeof exchangeRates['G$'] === 'number' ? exchangeRates['G$'].toFixed(0) : '7500' }}</span>
                </div>
                <div class="rate-item">
                  <span class="rate-label">USD → R$</span>
                  <span class="rate-value">{{ typeof exchangeRates['R$'] === 'number' ? exchangeRates['R$'].toFixed(2) : '5.85' }}</span>
                </div>
              </div>
              <p class="rate-updated" v-if="lastUpdated">
                Atualizado: {{ formatDate(lastUpdated) }}
              </p>
              <p v-if="ratesError" class="rate-error">{{ ratesError }}</p>
            </div>
          </div>

          <!-- Quick Actions -->
          <div class="action-card wide">
            <h3 class="card-title">{{ $t('dashboard.quickActions') }}</h3>
            <div class="quick-actions">
              <button class="action-button primary">
                <div class="action-icon">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                </div>
                <span>{{ $t('dashboard.newSale') }}</span>
              </button>

              <button class="action-button green">
                <div class="action-icon">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                </div>
                <span>{{ $t('dashboard.manageVendors') }}</span>
              </button>

              <button class="action-button purple">
                <div class="action-icon">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
                  </svg>
                </div>
                <span>{{ $t('dashboard.viewOrders') }}</span>
              </button>

              <button class="action-button yellow">
                <div class="action-icon">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <span>{{ $t('dashboard.reports') }}</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Recent Activity -->
        <div class="activity-grid">
          <!-- Recent Sales -->
          <div class="activity-card">
            <div class="card-header">
              <h3 class="card-title">{{ $t('dashboard.recentSales') }}</h3>
              <button class="view-all-button">{{ $t('common.viewAll') }}</button>
            </div>
            
            <div v-if="dashboardStore.recentSales.length === 0" class="empty-state">
              <svg class="empty-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              <p class="empty-title">{{ $t('dashboard.noRecentSales') }}</p>
              <p class="empty-subtitle">{{ $t('dashboard.salesWillAppear') }}</p>
            </div>
            
            <div v-else class="sales-list">
              <div
                v-for="sale in dashboardStore.recentSales"
                :key="sale.id"
                class="sale-item"
              >
                <div class="sale-info">
                  <p class="sale-product">{{ sale.descricao_produto || $t('dashboard.productSale') }}</p>
                  <p class="sale-details">{{ sale.vendedor_nome || $t('dashboard.unknownVendor') }} • {{ formatDate(sale.data_venda) }}</p>
                </div>
                <div class="sale-amount">
                  <p class="sale-value">{{ sale.moeda }} {{ formatOriginalCurrency(sale.valor_liquido) }}</p>
                  <p class="sale-method">{{ sale.metodo_pagamento }}</p>
                </div>
              </div>
            </div>
          </div>

          <!-- System Status -->
          <div class="activity-card">
            <h3 class="card-title">{{ $t('dashboard.systemStatus') }}</h3>
            <div class="status-grid">
              <div class="status-box">
                <div class="status-icon online">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12l5 5L20 7"></path>
                  </svg>
                </div>
                <div class="status-info">
                  <span class="status-label">API</span>
                  <span class="status-value online">Online</span>
                </div>
              </div>
              
              <div class="status-box">
                <div class="status-icon online">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.79 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.79 4 8 4s8-1.79 8-4M4 7c0-2.21 3.79-4 8-4s8 1.79 8 4"></path>
                  </svg>
                </div>
                <div class="status-info">
                  <span class="status-label">Database</span>
                  <span class="status-value online">Connected</span>
                </div>
              </div>
              
              <div class="status-box">
                <div class="status-icon warning">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1"></path>
                  </svg>
                </div>
                <div class="status-info">
                  <span class="status-label">Exchange</span>
                  <span class="status-value warning">{{ getLastUpdateTime }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- Footer -->
    <footer class="dashboard-footer">
      <div class="footer-content">
        <div class="footer-left">
          <div class="footer-info">
            <span class="footer-brand">ERP Eleven</span>
            <span class="footer-version">v1.0.0</span>
            <span class="footer-version">Developed by lucasadrianof</span>
          </div>
        </div>
        
        <div class="footer-center">
          <div class="footer-status">
            <span class="system-status-indicator"></span>
            <span class="system-status-text">System Online</span>
          </div>
        </div>
        
        <div class="footer-right">
          <div class="footer-links">
            <button class="footer-link">{{ $t('footer.help') }}</button>
            <button class="footer-link">{{ $t('footer.settings') }}</button>
            <button class="footer-link">{{ $t('footer.about') }}</button>
          </div>
        </div>
      </div>
    </footer>


    <!-- Exchange Rate Modal -->
    <div v-if="showExchangeRateModal || showExchangeRateHeaderModal" class="modal-overlay" @click="closeExchangeRateModals">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h2>Editar Taxas de Câmbio</h2>
          <button @click="closeExchangeRateModals" class="modal-close">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="modal-body">
          <div v-if="exchangeRateError" class="alert alert-error">
            {{ exchangeRateError }}
          </div>

          <div class="rate-form">
            <div class="form-group">
              <label for="usd_to_pyg">USD → Guarani (G$)</label>
              <input 
                id="usd_to_pyg"
                type="number" 
                step="0.01"
                v-model.number="editingRates.usd_to_pyg"
                placeholder="7500.0000"
                class="form-input"
              />
            </div>

            <div class="form-group">
              <label for="usd_to_brl">USD → Real (R$)</label>
              <input 
                id="usd_to_brl"
                type="number" 
                step="0.01"
                v-model.number="editingRates.usd_to_brl"
                placeholder="5.85"
                class="form-input"
              />
            </div>

            <div class="form-group">
              <label for="eur_to_usd">EUR → USD ($)</label>
              <input 
                id="eur_to_usd"
                type="number" 
                step="0.0001"
                v-model.number="editingRates.eur_to_usd"
                placeholder="1.0850"
                class="form-input"
              />
            </div>

            <div class="form-group">
              <label for="eur_to_brl">EUR → Real (R$)</label>
              <input 
                id="eur_to_brl"
                type="number" 
                step="0.01"
                v-model.number="editingRates.eur_to_brl"
                placeholder="6.20"
                class="form-input"
              />
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button @click="closeExchangeRateModals" class="btn btn-secondary">
            Cancelar
          </button>
          <button @click="saveExchangeRates" :disabled="isLoadingRates" class="btn btn-primary">
            <span v-if="isLoadingRates">Salvando...</span>
            <span v-else>Salvar Taxas</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useDashboardStore } from '@/stores/dashboard'
import { useCurrencyStore } from '@/stores/currency'
import { availableLocales, setLocale } from '@/i18n'
import type { CurrencyCode } from '@/stores/currency'

const router = useRouter()
const { locale, t } = useI18n()
const authStore = useAuthStore()
const dashboardStore = useDashboardStore()
const currencyStore = useCurrencyStore()

const currentTime = ref('')
const timeUpdateTrigger = ref(0) // Para forçar atualizações do getLastUpdateTime
const showCurrencyDropdown = ref(false)
const showLanguageDropdown = ref(false)
const showExchangeRateModal = ref(false)
const showExchangeRateHeaderModal = ref(false)
const exchangeRateError = ref<string | null>(null)

// Exchange rate state (local to avoid dependency issues)
const isLoadingRates = ref(false)
const ratesError = ref<string | null>(null)
const lastUpdated = ref<string | null>(null)
const exchangeRates = ref<Record<string, number>>({
  'G$': 7500.0,
  'R$': 5.85,
  'USD': 1.0,
  'EUR': 0.92
})

// Exchange rate editing
const editingRates = ref({
  usd_to_pyg: 0,
  usd_to_brl: 0,
  eur_to_usd: 0,
  eur_to_brl: 0
})

// Check if user can edit rates
const canEditRates = computed(() => {
  return authStore.user && ['ADMIN', 'GERENTE'].includes(authStore.user.role)
})

const currentLocale = computed(() => locale.value)
const getCurrentLanguage = computed(() => {
  return availableLocales.find(lang => lang.code === currentLocale.value)
})

const updateTime = () => {
  currentTime.value = new Date().toLocaleString('en-US', {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
  
  // Update trigger to force reactivity of getLastUpdateTime every minute
  const seconds = new Date().getSeconds()
  if (seconds === 0) {
    timeUpdateTrigger.value++
  }
}

const formatCurrency = (value: number, fromCurrency: CurrencyCode = 'R$') => {
  // Convert from the original currency (usually R$) to the selected currency
  const convertedValue = currencyStore.convertBetweenCurrencies(value, fromCurrency, currencyStore.selectedCurrency)
  return currencyStore.formatCurrency(convertedValue)
}

const formatOriginalCurrency = (value: number) => {
  // Format the original value without currency conversion for financial transparency
  return value.toLocaleString('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('pt-BR')
}

const handleLogout = async () => {
  await authStore.logout()
  router.push('/login')
}

const toggleCurrencyDropdown = () => {
  showCurrencyDropdown.value = !showCurrencyDropdown.value
  showLanguageDropdown.value = false
}

const toggleLanguageDropdown = () => {
  showLanguageDropdown.value = !showLanguageDropdown.value
  showCurrencyDropdown.value = false
}

const handleCurrencyChange = (currencyCode: CurrencyCode) => {
  currencyStore.setSelectedCurrency(currencyCode)
  showCurrencyDropdown.value = false
  // Refresh dashboard data to reflect currency changes
  dashboardStore.refreshData()
}

const handleLanguageChange = (langCode: string) => {
  setLocale(langCode)
  showLanguageDropdown.value = false
}

// Exchange Rate Modal Functions
const openCardModal = () => {
  if (!canEditRates.value) return
  showExchangeRateModal.value = true
  loadCurrentRatesToEdit()
}

const handleHeaderClick = () => {
  if (!canEditRates.value) return
  showExchangeRateHeaderModal.value = true
  loadCurrentRatesToEdit()
}


const closeExchangeRateModals = () => {
  showExchangeRateModal.value = false
  showExchangeRateHeaderModal.value = false
  exchangeRateError.value = null
}

const getLastUpdateTime = computed(() => {
  // Force reactivity with trigger
  timeUpdateTrigger.value
  
  if (!lastUpdated.value) {
    return 'Nunca'
  }
  
  const lastUpdate = new Date(lastUpdated.value)
  const now = new Date()
  const diffInMinutes = Math.floor((now.getTime() - lastUpdate.getTime()) / (1000 * 60))
  
  if (diffInMinutes < 1) {
    return 'agora mesmo'
  } else if (diffInMinutes < 60) {
    return `há ${diffInMinutes}min`
  } else if (diffInMinutes < 1440) {
    const hours = Math.floor(diffInMinutes / 60)
    return `há ${hours}h`
  } else {
    const days = Math.floor(diffInMinutes / 1440)
    return `há ${days}d`
  }
})

const navigateToExchangeRates = () => {
  router.push('/exchange-rates')
}

// Load exchange rates from API
const loadExchangeRates = async () => {
  try {
    isLoadingRates.value = true
    ratesError.value = null
    
    // Import exchangeRateAPI dynamically to avoid circular dependency
    const { exchangeRateAPI } = await import('@/services/api')
    const response = await exchangeRateAPI.getCurrentRates()
    
    // Update local state with API data
    if (response.usd_to_pyg) exchangeRates.value['G$'] = Number(response.usd_to_pyg)
    if (response.usd_to_brl) exchangeRates.value['R$'] = Number(response.usd_to_brl)
    if (response.last_updated) lastUpdated.value = response.last_updated
    
  } catch (error: any) {
    ratesError.value = error.message || 'Erro ao carregar taxas de câmbio'
  } finally {
    isLoadingRates.value = false
  }
}

const loadCurrentRatesToEdit = () => {
  editingRates.value = {
    usd_to_pyg: exchangeRates.value['G$'],
    usd_to_brl: exchangeRates.value['R$'],
    eur_to_usd: 1.0850, // Default values
    eur_to_brl: 6.20
  }
}

const saveExchangeRates = async () => {
  try {
    exchangeRateError.value = null
    isLoadingRates.value = true
    
    // Import exchangeRateAPI directly
    const { exchangeRateAPI } = await import('@/services/api')
    
    if (!authStore.user) {
      throw new Error('User not authenticated')
    }

    await exchangeRateAPI.quickUpdate({
      usd_to_pyg: editingRates.value.usd_to_pyg || undefined,
      usd_to_brl: editingRates.value.usd_to_brl || undefined,
      eur_to_usd: editingRates.value.eur_to_usd || undefined,
      eur_to_brl: editingRates.value.eur_to_brl || undefined,
      source: 'Dashboard',
      updated_by: authStore.user.nome,
      notes: 'Updated from dashboard'
    })
    
    // Reload rates after successful update
    await loadExchangeRates()
    closeExchangeRateModals()
    
  } catch (error: any) {
    exchangeRateError.value = error.message || 'Erro ao salvar as taxas de câmbio'
  } finally {
    isLoadingRates.value = false
  }
}

// Close dropdowns when clicking outside
const handleClickOutside = (event: Event) => {
  const target = event.target as HTMLElement
  if (!target.closest('.dropdown')) {
    showCurrencyDropdown.value = false
    showLanguageDropdown.value = false
  }
}

let timeInterval: NodeJS.Timeout

onMounted(async () => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
  document.addEventListener('click', handleClickOutside)
  
  // Load exchange rates and dashboard data
  await Promise.all([
    loadExchangeRates(),
    dashboardStore.refreshData()
  ])
})

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
  }
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  background-color: #f9fafb;
}

.dashboard-header {
  background-color: white;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
  border-bottom: 1px solid #e5e7eb;
  position: sticky;
  top: 0;
  z-index: 1000;
}

.header-content {
  padding: 1rem 1.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.app-logo {
  width: 2.5rem;
  height: 2.5rem;
  background-color: #2563eb;
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-icon {
  width: 1.5rem;
  height: 1.5rem;
  color: white;
}

.app-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #111827;
}

.welcome-text {
  margin: 0;
  font-size: 0.875rem;
  color: #6b7280;
}

.header-right {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex: 1;
}

.header-left-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.header-right-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.currency-language-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.header-control {
  position: relative;
}

.header-dropdown-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background-color: #f9fafb;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  cursor: pointer;
  font-size: 0.875rem;
  transition: all 0.2s;
  color: #6b7280;
}

.header-dropdown-button:hover {
  background-color: #f3f4f6;
  border-color: #9ca3af;
  color: #374151;
}

.header-dropdown-button:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.control-flag {
  font-size: 0.875rem;
  width: 1.25rem;
  display: inline-block;
}

.control-text {
  font-size: 0.875rem;
  font-weight: 500;
}

.header-dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  left: 0;
  background-color: white;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  z-index: 50;
  margin-top: 0.25rem;
  max-height: 200px;
  overflow-y: auto;
  min-width: 200px;
}

.header-dropdown-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.75rem;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.875rem;
  text-align: left;
  transition: background-color 0.2s;
}

.header-dropdown-item:hover {
  background-color: #f9fafb;
}

.header-dropdown-item.active {
  background-color: #eff6ff;
  color: #2563eb;
}

.current-time {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: #6b7280;
}

.time-icon {
  width: 1rem;
  height: 1rem;
}

.divider {
  width: 1px;
  height: 1.5rem;
  background-color: #d1d5db;
}

.logout-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem;
  background: none;
  border: none;
  color: #6b7280;
  cursor: pointer;
  font-size: 0.875rem;
  transition: color 0.2s;
}

.logout-button:hover {
  color: #111827;
}

.logout-icon {
  width: 1rem;
  height: 1rem;
}

.dashboard-main {
  padding: 1.5rem 1.5rem 2rem;
}

.loading-container {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 5rem 0;
}

.loading-content {
  text-align: center;
}

.loading-spinner {
  width: 2rem;
  height: 2rem;
  color: #2563eb;
  margin: 0 auto 0.5rem;
  animation: spin 1s linear infinite;
}

.spinner-track {
  opacity: 0.25;
}

.spinner-path {
  opacity: 0.75;
}

.loading-content p {
  margin: 0;
  font-size: 0.875rem;
  color: #6b7280;
}

.dashboard-content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
}

.stat-card {
  background-color: white;
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
  padding: 1.5rem;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.stat-icon {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon svg {
  width: 1.5rem;
  height: 1.5rem;
}

.stat-icon.green {
  background-color: #dcfce7;
  color: #16a34a;
}

.stat-icon.blue {
  background-color: #dbeafe;
  color: #2563eb;
}

.stat-icon.purple {
  background-color: #f3e8ff;
  color: #9333ea;
}

.stat-icon.yellow {
  background-color: #fef3c7;
  color: #d97706;
}

.stat-label {
  margin: 0 0 0.25rem 0;
  font-size: 0.875rem;
  font-weight: 500;
  color: #6b7280;
}

.stat-value {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: #111827;
}

.actions-grid {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 1.5rem;
}

.action-card {
  background-color: white;
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
  padding: 1rem;
  transition: all 0.2s;
}

.action-card.exchange-rate-card:hover {
  border-color: #2563eb;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.card-title {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 500;
  color: #111827;
}

.card-icon {
  width: 2rem;
  height: 2rem;
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-icon svg {
  width: 1.25rem;
  height: 1.25rem;
}

.exchange-rate {
  text-align: center;
  padding: 1rem 0;
}

.rate-value {
  margin: 0 0 0.25rem 0;
  font-size: 1.875rem;
  font-weight: 700;
  color: #111827;
}

.rate-label {
  margin: 0;
  font-size: 0.875rem;
  color: #6b7280;
}

.quick-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.action-button {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  border: none;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: background-color 0.2s;
  gap: 0.5rem;
}

.action-button.primary {
  background-color: #eff6ff;
  color: #2563eb;
}

.action-button.primary:hover {
  background-color: #dbeafe;
}

.action-button.green {
  background-color: #f0fdf4;
  color: #16a34a;
}

.action-button.green:hover {
  background-color: #dcfce7;
}

.action-button.purple {
  background-color: #faf5ff;
  color: #9333ea;
}

.action-button.purple:hover {
  background-color: #f3e8ff;
}

.action-button.yellow {
  background-color: #fffbeb;
  color: #d97706;
}

.action-button.yellow:hover {
  background-color: #fef3c7;
}

.action-icon {
  width: 2.5rem;
  height: 2.5rem;
  background-color: currentColor;
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.action-icon svg {
  width: 1.5rem;
  height: 1.5rem;
}

.action-button span {
  font-size: 0.875rem;
  font-weight: 500;
}

.activity-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

.activity-card {
  background-color: white;
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
  padding: 1rem;
}

.view-all-button {
  background: none;
  border: none;
  color: #2563eb;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
}

.view-all-button:hover {
  color: #1d4ed8;
}

.empty-state {
  text-align: center;
  padding: 2rem 0;
}

.empty-icon {
  width: 3rem;
  height: 3rem;
  color: #9ca3af;
  margin: 0 auto 0.5rem;
}

.empty-title {
  margin: 0 0 0.25rem 0;
  font-size: 0.875rem;
  color: #6b7280;
}

.empty-subtitle {
  margin: 0;
  font-size: 0.75rem;
  color: #9ca3af;
}

.sales-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.sale-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 0;
  border-bottom: 1px solid #f3f4f6;
}

.sale-item:last-child {
  border-bottom: none;
}

.sale-product {
  margin: 0 0 0.25rem 0;
  font-size: 0.875rem;
  font-weight: 500;
  color: #111827;
}

.sale-details {
  margin: 0;
  font-size: 0.75rem;
  color: #6b7280;
}

.sale-amount {
  text-align: right;
}

.sale-value {
  margin: 0 0 0.25rem 0;
  font-size: 0.875rem;
  font-weight: 600;
  color: #111827;
}

.sale-method {
  margin: 0;
  font-size: 0.75rem;
  color: #6b7280;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
}

.status-box {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 0.5rem;
  border: 1px solid #e5e7eb;
  transition: all 0.2s;
}

.status-box:hover {
  border-color: #d1d5db;
  background-color: #f9fafb;
}

.status-icon {
  width: 2rem;
  height: 2rem;
  border-radius: 0.375rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.status-icon svg {
  width: 1rem;
  height: 1rem;
}

.status-icon.online {
  background-color: #dcfce7;
  color: #16a34a;
}

.status-icon.warning {
  background-color: #fef3c7;
  color: #d97706;
}

.status-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.status-info .status-label {
  font-size: 0.75rem;
  color: #6b7280;
  font-weight: 500;
  line-height: 1.2;
}

.status-info .status-value {
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1.2;
}

.status-info .status-value.online {
  color: #16a34a;
}

.status-info .status-value.warning {
  color: #d97706;
}


/* Footer Styles */
.dashboard-footer {
  background-color: white;
  border-top: 1px solid #e5e7eb;
  padding: 1rem 1.5rem;
  margin-top: auto;
}

.footer-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 1200px;
  margin: 0 auto;
}

.footer-left {
  display: flex;
  align-items: center;
}

.footer-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.footer-brand {
  font-weight: 600;
  color: #2563eb;
  font-size: 0.875rem;
}

.footer-version {
  font-size: 0.75rem;
  color: #6b7280;
  background-color: #f3f4f6;
  padding: 0.125rem 0.5rem;
  border-radius: 0.75rem;
}

.footer-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.footer-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.system-status-indicator {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  background-color: #10b981;
}

.system-status-text {
  font-size: 0.875rem;
  color: #6b7280;
}

.footer-controls {
  display: flex;
  align-items: center;
  gap: 2rem;
}

.control-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  position: relative;
}

.control-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: #6b7280;
  text-align: center;
}

.dropdown {
  position: relative;
}

.dropdown-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background-color: #f9fafb;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  cursor: pointer;
  font-size: 0.875rem;
  transition: all 0.2s;
  min-width: 120px;
  justify-content: space-between;
}

.dropdown-button:hover {
  background-color: #f3f4f6;
  border-color: #9ca3af;
}

.dropdown-button:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.dropdown-icon {
  width: 1rem;
  height: 1rem;
  color: #6b7280;
  transition: transform 0.2s;
}

.dropdown-icon.rotate {
  transform: rotate(180deg);
}

.currency-flag,
.language-flag {
  font-size: 1rem;
  width: 1.25rem;
  display: inline-block;
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background-color: white;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  z-index: 50;
  margin-top: 0.25rem;
  max-height: 200px;
  overflow-y: auto;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.75rem;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.875rem;
  text-align: left;
  transition: background-color 0.2s;
}

.dropdown-item:hover {
  background-color: #f9fafb;
}

.dropdown-item.active {
  background-color: #eff6ff;
  color: #2563eb;
}

.currency-info {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.currency-code {
  font-weight: 500;
  line-height: 1;
}

.currency-name {
  font-size: 0.75rem;
  color: #6b7280;
  line-height: 1;
}

.language-name {
  font-weight: 500;
}

.footer-right {
  display: flex;
  align-items: center;
}

.footer-links {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.footer-link {
  background: none;
  border: none;
  color: #6b7280;
  font-size: 0.875rem;
  cursor: pointer;
  transition: color 0.2s;
}

.footer-link:hover {
  color: #2563eb;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* Exchange Rate Styles */
.card-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.navigation-arrow {
  width: 1.5rem;
  height: 1.5rem;
  color: #9ca3af;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.7;
  transition: all 0.2s;
}

.exchange-rate-card:hover .navigation-arrow {
  color: #2563eb;
  opacity: 1;
  transform: translateX(2px);
}

.navigation-arrow svg {
  width: 1rem;
  height: 1rem;
}

.edit-rate-btn {
  width: 1.5rem;
  height: 1.5rem;
  border-radius: 0.375rem;
  background-color: #f3f4f6;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  transition: all 0.2s;
}

.edit-rate-btn:hover {
  background-color: #e5e7eb;
  color: #374151;
}

.edit-rate-btn svg {
  width: 1rem;
  height: 1rem;
}

.rate-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.rate-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.rate-label {
  font-size: 0.75rem;
  color: #6b7280;
  margin-bottom: 0.25rem;
}

.rate-value {
  font-size: 1.25rem;
  font-weight: 600;
  color: #111827;
}

.rate-updated {
  font-size: 0.75rem;
  color: #6b7280;
  text-align: center;
  margin: 0;
}

.rate-error {
  font-size: 0.75rem;
  color: #dc2626;
  text-align: center;
  margin: 0;
}

.rate-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem 0;
}

.rate-loading .loading-spinner {
  width: 1.5rem;
  height: 1.5rem;
  color: #2563eb;
  animation: spin 1s linear infinite;
}

.rate-loading p {
  font-size: 0.875rem;
  color: #6b7280;
  margin: 0;
}

/* Header Exchange Rate Display */
.exchange-rates-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background-color: #f9fafb;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  transition: all 0.2s;
}

.exchange-rates-header.editable {
  cursor: pointer;
}

.exchange-rates-header.editable:hover {
  background-color: #f3f4f6;
  border-color: #9ca3af;
}

.rates-display {
  display: flex;
  gap: 0.75rem;
}

.rate-item-header {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.rate-flag {
  font-size: 0.75rem;
}

.rate-value-header {
  font-size: 0.875rem;
  font-weight: 500;
  color: #111827;
}

.edit-icon {
  width: 1rem;
  height: 1rem;
  color: #6b7280;
}

/* Modal Styles */
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
}

.modal-content {
  background-color: white;
  border-radius: 0.75rem;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
  max-width: 500px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  margin: 1rem;
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
  max-height: 60vh;
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

/* Form Styles */
.rate-form {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
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

.btn {
  padding: 0.75rem 1.5rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-primary {
  background-color: #2563eb;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: #1d4ed8;
}

.btn-primary:disabled {
  background-color: #9ca3af;
  cursor: not-allowed;
}

.btn-secondary {
  background-color: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
}

.btn-secondary:hover {
  background-color: #e5e7eb;
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

/* Responsive visibility classes */
.desktop-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.mobile-controls {
  display: none;
}

@media (max-width: 768px) {
  /* Toggle visibility classes for mobile */
  .desktop-controls {
    display: none !important;
  }
  
  .mobile-controls {
    display: block !important;
  }

  .mobile-controls .currency-language-group {
    margin-bottom: 1rem;
  }

  /* Ocultar data/hora no mobile */
  .current-time {
    display: none !important;
  }

  /* Reduzir botão de edição de câmbio no mobile */
  .edit-rate-btn {
    width: 1.25rem !important;
    height: 1.25rem !important;
    border-radius: 0.25rem !important;
  }
  
  .edit-rate-btn svg {
    width: 0.75rem !important;
    height: 0.75rem !important;
  }

  /* Reduzir card Taxa de Câmbio para ficar igual aos outros */
  .action-card.exchange-rate-card {
    padding: 0.875rem !important;
  }
  
  .action-card.exchange-rate-card .exchange-rate {
    padding: 0.5rem 0 !important;
    text-align: center;
  }
  
  .action-card.exchange-rate-card .rate-item {
    margin-bottom: 0.375rem !important;
  }
  
  .action-card.exchange-rate-card .rate-value {
    font-size: 1.125rem !important;
    margin: 0 0 0.125rem 0 !important;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }
  
  .actions-grid,
  .activity-grid {
    grid-template-columns: 1fr;
  }
  
  .quick-actions {
    grid-template-columns: 1fr 1fr;
  }
  
  .header-content {
    flex-direction: column;
    gap: 1rem;
  }
  
  .header-right {
    width: 100%;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .header-left-controls {
    flex-direction: column;
    gap: 0.5rem;
    align-items: flex-start;
  }

  .currency-language-group {
    gap: 0.25rem;
  }

  .header-right-controls {
    gap: 0.5rem;
  }

  .header-control {
    flex-shrink: 0;
  }

  .header-dropdown-button {
    padding: 0.375rem 0.5rem;
    font-size: 0.75rem;
    min-width: 80px;
  }

  .header-dropdown-menu {
    min-width: 150px;
  }

  .footer-content {
    flex-direction: column;
    gap: 1rem;
  }

  .footer-controls {
    gap: 1rem;
  }

  .control-group {
    align-items: center;
  }

  .dropdown-button {
    min-width: 100px;
    font-size: 0.75rem;
  }

  .footer-links {
    gap: 0.5rem;
  }

  .footer-link {
    font-size: 0.75rem;
  }

  .rate-form {
    grid-template-columns: 1fr;
  }

  .rates-display {
    flex-direction: row;
    gap: 0.5rem;
  }

  .exchange-rates-header {
    padding: 0.5rem;
  }

  .modal-content {
    margin: 0.5rem;
    max-height: 95vh;
  }

  .modal-header,
  .modal-body,
  .modal-footer {
    padding: 1rem;
  }
}
</style>