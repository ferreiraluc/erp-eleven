<!-- Example of how to integrate Exchange Rate components in Dashboard -->
<template>
  <div class="dashboard">
    <!-- Header with Exchange Rate Display -->
    <header class="dashboard-header">
      <div class="header-content">
        <h1>Dashboard - ERP Eleven</h1>
        <div class="user-info">
          <span>{{ user?.name }}</span>
          <span class="role-badge" :class="user?.role">{{ user?.role }}</span>
        </div>
      </div>
      
      <!-- Exchange Rate Header Component -->
      <ExchangeRateHeader />
    </header>

    <!-- Main Dashboard Content -->
    <main class="dashboard-main">
      <div class="dashboard-grid">
        <!-- Sales Stats Card -->
        <div class="stat-card sales">
          <div class="stat-icon">📊</div>
          <div class="stat-content">
            <h3>Vendas Hoje</h3>
            <p class="stat-value">{{ todaySales }}</p>
            <span class="stat-change positive">+12%</span>
          </div>
        </div>

        <!-- Revenue Card -->
        <div class="stat-card revenue">
          <div class="stat-icon">💰</div>
          <div class="stat-content">
            <h3>Receita Mensal</h3>
            <p class="stat-value">R$ {{ monthlyRevenue }}</p>
            <span class="stat-change positive">+8.2%</span>
          </div>
        </div>

        <!-- Orders Card -->
        <div class="stat-card orders">
          <div class="stat-icon">📦</div>
          <div class="stat-content">
            <h3>Pedidos Pendentes</h3>
            <p class="stat-value">{{ pendingOrders }}</p>
            <span class="stat-change neutral">--</span>
          </div>
        </div>

        <!-- Exchange Rate Card - Expandable -->
        <ExchangeRateCard class="exchange-card" />

        <!-- Sales Chart -->
        <div class="chart-card">
          <h3>Vendas por Período</h3>
          <!-- Your existing sales chart here -->
          <div class="chart-placeholder">
            📈 Gráfico de vendas
          </div>
        </div>

        <!-- Recent Activities -->
        <div class="activity-card">
          <h3>Atividades Recentes</h3>
          <div class="activity-list">
            <div v-for="activity in recentActivities" :key="activity.id" class="activity-item">
              <div class="activity-icon">{{ activity.icon }}</div>
              <div class="activity-content">
                <p class="activity-title">{{ activity.title }}</p>
                <span class="activity-time">{{ formatTime(activity.timestamp) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- Weekly Closing Modal (for Saturday operations) -->
    <WeeklyClosingModal 
      v-if="showWeeklyClosing" 
      @close="showWeeklyClosing = false"
      @confirm="processWeeklyClosing"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useExchangeRateStore } from '@/stores/exchangeRate'
import { useDashboardStore } from '@/stores/dashboard'
import ExchangeRateHeader from './ExchangeRateHeader.vue'
import ExchangeRateCard from './ExchangeRateCard.vue'
import WeeklyClosingModal from './WeeklyClosingModal.vue'

const authStore = useAuthStore()
const exchangeStore = useExchangeRateStore()
const dashboardStore = useDashboardStore()

const showWeeklyClosing = ref(false)

// Computed properties
const user = computed(() => authStore.user)

const todaySales = computed(() => dashboardStore.stats.vendasHoje || 0)
const monthlyRevenue = computed(() => {
  return (dashboardStore.stats.totalVendas || 0).toLocaleString('pt-BR', {
    minimumFractionDigits: 2
  })
})
const pendingOrders = computed(() => dashboardStore.stats.totalPedidos || 0)

const recentActivities = ref([
  {
    id: 1,
    icon: '🏪',
    title: 'Nova venda registrada - R$ 450,00',
    timestamp: new Date()
  },
  {
    id: 2,
    icon: '💱',
    title: 'Taxa de câmbio atualizada - USD→BRL',
    timestamp: new Date(Date.now() - 15 * 60 * 1000)
  },
  {
    id: 3,
    icon: '📦',
    title: 'Pedido #PED-2025-000123 enviado',
    timestamp: new Date(Date.now() - 30 * 60 * 1000)
  },
  {
    id: 4,
    icon: '👤',
    title: 'Novo vendedor cadastrado',
    timestamp: new Date(Date.now() - 45 * 60 * 1000)
  }
])

// Methods
const formatTime = (timestamp: Date) => {
  const now = new Date()
  const diff = now.getTime() - timestamp.getTime()
  const minutes = Math.floor(diff / (1000 * 60))
  
  if (minutes < 1) return 'Agora'
  if (minutes < 60) return `${minutes}min atrás`
  
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h atrás`
  
  return timestamp.toLocaleDateString('pt-BR')
}

const checkWeeklyClosing = () => {
  const today = new Date()
  const isSaturday = today.getDay() === 6 // Saturday = 6
  const hour = today.getHours()
  
  // Check if it's Saturday evening and user is admin/manager
  if (isSaturday && hour >= 18 && (user.value?.role === 'ADMIN' || user.value?.role === 'GERENTE')) {
    // Check if weekly closing was already done today
    const lastClosing = localStorage.getItem('lastWeeklyClosing')
    const todayStr = today.toDateString()
    
    if (lastClosing !== todayStr) {
      showWeeklyClosing.value = true
    }
  }
}

const processWeeklyClosing = async (data: any) => {
  try {
    // Get weekly averages for all currency pairs
    const saturday = new Date()
    saturday.setDate(saturday.getDate() - saturday.getDay() + 6) // Get this week's Saturday
    
    const weeklyAverages = await exchangeStore.getSalesWeekAverage(
      saturday.toISOString().split('T')[0]
    )
    
    // Process weekly closing with exchange rate averages
    const closingData = {
      ...data,
      exchangeRateAverages: weeklyAverages,
      closingDate: saturday.toISOString().split('T')[0]
    }
    
    // Save weekly closing (implement this in your dashboard store)
    await dashboardStore.processWeeklyClosing(closingData)
    
    // Mark as done for today
    localStorage.setItem('lastWeeklyClosing', new Date().toDateString())
    
    showWeeklyClosing.value = false
    
  } catch (error) {
    console.error('Error processing weekly closing:', error)
  }
}

// Lifecycle
onMounted(async () => {
  // Load dashboard data
  await Promise.all([
    dashboardStore.fetchStats(),
    exchangeStore.fetchCurrentRates()
  ])
  
  // Check if weekly closing is needed
  checkWeeklyClosing()
})
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  background: #f8fafc;
}

.dashboard-header {
  background: white;
  padding: 16px 24px;
  border-bottom: 1px solid #e2e8f0;
  margin-bottom: 24px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-content h1 {
  margin: 0;
  color: #1a202c;
  font-size: 1.5rem;
  font-weight: 600;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.role-badge {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.role-badge.ADMIN {
  background: #fecaca;
  color: #991b1b;
}

.role-badge.GERENTE {
  background: #fed7aa;
  color: #9a3412;
}

.role-badge.VENDEDOR {
  background: #bbf7d0;
  color: #166534;
}

.dashboard-main {
  padding: 0 24px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.stat-card {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  font-size: 2rem;
  opacity: 0.8;
}

.stat-content h3 {
  margin: 0 0 4px 0;
  color: #6b7280;
  font-size: 0.875rem;
  font-weight: 500;
}

.stat-value {
  margin: 0 0 4px 0;
  font-size: 1.5rem;
  font-weight: 700;
  color: #1a202c;
}

.stat-change {
  font-size: 0.75rem;
  font-weight: 500;
}

.stat-change.positive {
  color: #059669;
}

.stat-change.negative {
  color: #dc2626;
}

.stat-change.neutral {
  color: #6b7280;
}

.exchange-card {
  grid-column: span 2;
}

.chart-card {
  grid-column: span 2;
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.chart-card h3 {
  margin: 0 0 16px 0;
  color: #1a202c;
  font-size: 1.125rem;
  font-weight: 600;
}

.chart-placeholder {
  height: 200px;
  background: #f1f5f9;
  border: 2px dashed #cbd5e1;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.125rem;
  color: #64748b;
}

.activity-card {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.activity-card h3 {
  margin: 0 0 16px 0;
  color: #1a202c;
  font-size: 1.125rem;
  font-weight: 600;
}

.activity-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.activity-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  border-radius: 8px;
  transition: background-color 0.2s;
}

.activity-item:hover {
  background: #f8fafc;
}

.activity-icon {
  font-size: 1.25rem;
}

.activity-content {
  flex: 1;
}

.activity-title {
  margin: 0 0 2px 0;
  color: #374151;
  font-size: 0.875rem;
  font-weight: 500;
}

.activity-time {
  color: #9ca3af;
  font-size: 0.75rem;
}

@media (max-width: 768px) {
  .dashboard-header {
    padding: 12px 16px;
  }
  
  .header-content {
    flex-direction: column;
    gap: 8px;
    align-items: stretch;
  }
  
  .dashboard-main {
    padding: 0 16px;
  }
  
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
  
  .exchange-card,
  .chart-card {
    grid-column: span 1;
  }
}
</style>