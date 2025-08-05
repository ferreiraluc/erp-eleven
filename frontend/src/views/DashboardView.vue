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
            <p class="welcome-text">Welcome back, {{ authStore.userName }}!</p>
          </div>
        </div>
        
        <div class="header-right">
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
            <span>Logout</span>
          </button>
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
          <p>Loading dashboard...</p>
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
                <p class="stat-label">Today's Sales</p>
                <p class="stat-value">R$ {{ formatCurrency(dashboardStore.stats?.total_sales_today || 0) }}</p>
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
                <p class="stat-label">Weekly Sales</p>
                <p class="stat-value">R$ {{ formatCurrency(dashboardStore.stats?.total_sales_week || 0) }}</p>
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
                <p class="stat-label">Pending Orders</p>
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
                <p class="stat-label">Active Vendors</p>
                <p class="stat-value">{{ dashboardStore.stats?.active_vendors || 0 }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Quick Actions -->
        <div class="actions-grid">
          <!-- Exchange Rate Card -->
          <div class="action-card">
            <div class="card-header">
              <h3 class="card-title">Exchange Rate</h3>
              <div class="card-icon green">
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 4V2a1 1 0 011-1h8a1 1 0 011 1v2m-9 0h10m-9 0v14a2 2 0 002 2h6a2 2 0 002-2V4M9 8h6" />
                </svg>
              </div>
            </div>
            <div class="exchange-rate">
              <p class="rate-value">{{ dashboardStore.stats?.exchange_rate_g_to_r || 0 }}</p>
              <p class="rate-label">G$ to R$ Rate</p>
            </div>
          </div>

          <!-- Quick Actions -->
          <div class="action-card wide">
            <h3 class="card-title">Quick Actions</h3>
            <div class="quick-actions">
              <button class="action-button primary">
                <div class="action-icon">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                </div>
                <span>New Sale</span>
              </button>

              <button class="action-button green">
                <div class="action-icon">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                </div>
                <span>Manage Vendors</span>
              </button>

              <button class="action-button purple">
                <div class="action-icon">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
                  </svg>
                </div>
                <span>View Orders</span>
              </button>

              <button class="action-button yellow">
                <div class="action-icon">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <span>Reports</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Recent Activity -->
        <div class="activity-grid">
          <!-- Recent Sales -->
          <div class="activity-card">
            <div class="card-header">
              <h3 class="card-title">Recent Sales</h3>
              <button class="view-all-button">View all</button>
            </div>
            
            <div v-if="dashboardStore.recentSales.length === 0" class="empty-state">
              <svg class="empty-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              <p class="empty-title">No recent sales found</p>
              <p class="empty-subtitle">Sales will appear here once they are created</p>
            </div>
            
            <div v-else class="sales-list">
              <div
                v-for="sale in dashboardStore.recentSales"
                :key="sale.id"
                class="sale-item"
              >
                <div class="sale-info">
                  <p class="sale-product">{{ sale.descricao_produto || 'Product sale' }}</p>
                  <p class="sale-details">{{ sale.vendedor_nome || 'Unknown vendor' }} • {{ formatDate(sale.data_venda) }}</p>
                </div>
                <div class="sale-amount">
                  <p class="sale-value">{{ sale.moeda }} {{ formatCurrency(sale.valor_liquido) }}</p>
                  <p class="sale-method">{{ sale.metodo_pagamento }}</p>
                </div>
              </div>
            </div>
          </div>

          <!-- System Status -->
          <div class="activity-card">
            <h3 class="card-title">System Status</h3>
            <div class="status-list">
              <div class="status-item">
                <div class="status-indicator online"></div>
                <span class="status-label">API Server</span>
                <span class="status-value online">Online</span>
              </div>
              
              <div class="status-item">
                <div class="status-indicator online"></div>
                <span class="status-label">Database</span>
                <span class="status-value online">Connected</span>
              </div>
              
              <div class="status-item">
                <div class="status-indicator warning"></div>
                <span class="status-label">Exchange Rates</span>
                <span class="status-value warning">Last updated 2h ago</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useDashboardStore } from '@/stores/dashboard'

const router = useRouter()
const authStore = useAuthStore()
const dashboardStore = useDashboardStore()

const currentTime = ref('')

const updateTime = () => {
  currentTime.value = new Date().toLocaleString('en-US', {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatCurrency = (value: number) => {
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

let timeInterval: NodeJS.Timeout

onMounted(async () => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
  
  await dashboardStore.refreshData()
})

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
  }
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
  gap: 1rem;
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
  padding: 1.5rem;
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
  padding: 1.5rem;
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

.status-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.status-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.status-indicator {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  margin-right: 0.75rem;
}

.status-indicator.online {
  background-color: #10b981;
}

.status-indicator.warning {
  background-color: #f59e0b;
}

.status-label {
  font-size: 0.875rem;
  color: #6b7280;
  flex: 1;
}

.status-value {
  font-size: 0.875rem;
  font-weight: 500;
}

.status-value.online {
  color: #10b981;
}

.status-value.warning {
  color: #f59e0b;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 768px) {
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
  }
}
</style>