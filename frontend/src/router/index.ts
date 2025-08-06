import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: () => {
        // Load auth data immediately to check authentication status
        const authStore = useAuthStore()
        authStore.loadStoredAuth()
        return authStore.isAuthenticated ? '/dashboard' : '/login'
      }
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { requiresGuest: true }
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('../views/DashboardView.vue'),
      meta: { requiresAuth: true }
    },
    // Catch all route
    {
      path: '/:pathMatch(.*)*',
      redirect: () => {
        const authStore = useAuthStore()
        authStore.loadStoredAuth()
        return authStore.isAuthenticated ? '/dashboard' : '/login'
      }
    }
  ],
})

// Navigation guards
router.beforeEach((to, _from, next) => {
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
      next('/dashboard')
    } else {
      next()
    }
  }
  // Public routes
  else {
    next()
  }
})

export default router