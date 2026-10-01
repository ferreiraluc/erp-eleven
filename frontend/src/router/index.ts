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
import PDVView from '@/views/PDVView.vue'
import FiadoView from '@/views/FiadoView.vue'

const router = createRouter({
  history: import.meta.env.PROD ? createWebHashHistory() : createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/conta', name: 'conta', component: () => import('@/views/AccountView.vue'), meta: { requiresAuth: true } },
    { path: '/usuarios', name: 'usuarios', component: () => import('@/views/UserManagementView.vue'), meta: { requiresAuth: true, requiresOwner: true } },
    { path: '/auditoria', name: 'auditoria', component: () => import('@/views/AuditView.vue'), meta: { requiresAuth: true, requiresOwner: true } },
    {path:'/bi-vendas',name:'bi-vendas',component:()=>import('@/views/SalesBiView.vue'),meta:{requiresAuth:true,requiresManager:true}},
    {path:'/enderecos',name:'enderecos',component:()=>import('@/views/AddressesView.vue'),meta:{requiresAuth:true,requiresManager:true}},
    {
      path: '/assistente',
      name: 'assistente',
      component: () => import('@/views/AssistantView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true }
    },
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
    {
      path: '/pdv',
      name: 'pdv',
      component: PDVView,
      meta: { requiresAuth: true }
    },
    {
      path: '/fiado',
      name: 'fiado',
      component: FiadoView,
      meta: { requiresAuth: true, requiresAllSales: true }
    },
    // Catch all route — redirect to dashboard if authenticated, otherwise login
    {
      path: '/:pathMatch(.*)*',
      redirect: () => {
        return '/dashboard'
      }
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

// A stored token is a hint, not proof of a live session or current permissions.
router.beforeEach(async (to) => {
  const auth = useAuthStore()
  const verified = await auth.ensureSession()
  if (to.meta.requiresAuth && !verified) return '/login'
  if (!verified) return true
  if (auth.user?.must_change_password && to.path !== '/conta') return '/conta'
  if (to.meta.requiresGuest) return '/dashboard'
  if (to.meta.requiresOwner && !auth.isOwner) return '/dashboard'
  if (to.meta.requiresAdmin && !auth.isOwner) return '/dashboard'
  if (to.meta.requiresManager && !['ADMIN', 'GERENTE'].includes(auth.user?.role || '')) return '/dashboard'
  if (to.meta.requiresAllSales && auth.ownSales) return '/dashboard'
  return true
})

export default router
