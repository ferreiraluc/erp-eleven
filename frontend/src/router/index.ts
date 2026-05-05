import { createRouter, createWebHistory, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LoginView from '@/views/LoginView.vue'
import DashboardView from '@/views/DashboardView.vue'
import ExchangeRateManagement from '@/views/ExchangeRateManagement.vue'
import RastreamentoView from '@/views/RastreamentoView.vue'
import VendorManagement from '@/views/VendorManagement.vue'
import VendasView from '@/views/VendasView.vue'
import PedidosView from '@/views/PedidosView.vue'
import InventoryListView from '@/views/inventory/InventoryListView.vue'
import ClientesView from '@/views/ClientesView.vue'

const router = createRouter({
  history: import.meta.env.PROD ? createWebHashHistory() : createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/login'
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { requiresGuest: true }
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: DashboardView,
      meta: { requiresAuth: true }
    },
    {
      path: '/exchange-rates',
      name: 'exchange-rates',
      component: ExchangeRateManagement,
      meta: { requiresAuth: true }
    },
    {
      path: '/rastreamento',
      name: 'rastreamento',
      component: RastreamentoView,
      meta: { requiresAuth: true }
    },
    {
      path: '/vendors',
      name: 'vendors',
      component: VendorManagement,
      meta: { requiresAuth: true }
    },
    {
      path: '/vendas',
      name: 'vendas',
      component: VendasView,
      meta: { requiresAuth: true }
    },
    {
      path: '/pedidos',
      name: 'pedidos',
      component: PedidosView,
      meta: { requiresAuth: true }
    },
    {
      path: '/inventory',
      name: 'inventory',
      component: InventoryListView,
      meta: { requiresAuth: true }
    },
    {
      path: '/clientes',
      name: 'clientes',
      component: ClientesView,
      meta: { requiresAuth: true }
    },
    // Catch all route
    {
      path: '/:pathMatch(.*)*',
      redirect: '/login'
    }
  ],
})

const LAST_ROUTE_KEY = 'erp_last_route'

// Save last authenticated route so we can restore it after a full reload
router.afterEach((to) => {
  if (to.meta.requiresAuth) {
    localStorage.setItem(LAST_ROUTE_KEY, to.fullPath)
  }
})

// Navigation guards
router.beforeEach(async (to, _from, next) => {
  try {
    const authStore = useAuthStore()

    // Load stored auth if not already loaded
    if (!authStore.token) {
      authStore.loadStoredAuth()
    }

    // Check if route requires authentication
    if (to.meta.requiresAuth) {
      if (authStore.isAuthenticated) {
        next()
      } else {
        next('/login')
      }
    }
    // Check if route requires guest (user not logged in)
    else if (to.meta.requiresGuest) {
      if (authStore.isAuthenticated) {
        // Restore the last visited page instead of always going to /dashboard
        const lastRoute = localStorage.getItem(LAST_ROUTE_KEY)
        next(lastRoute || '/dashboard')
      } else {
        next()
      }
    }
    // Public routes
    else {
      next()
    }
  } catch (error) {
    console.error('Router navigation error:', error)
    next('/login')
  }
})

export default router