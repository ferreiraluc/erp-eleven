import { createRouter, createWebHistory, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LoginView from '@/views/LoginView.vue'
import SimpleLoginView from '@/views/SimpleLoginView.vue'
import DashboardView from '@/views/DashboardView.vue'
import TestView from '@/views/TestView.vue'

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
      component: SimpleLoginView,
      meta: { requiresGuest: true }
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: DashboardView,
      meta: { requiresAuth: true }
    },
    // Catch all route
    {
      path: '/:pathMatch(.*)*',
      redirect: '/login'
    }
  ],
})

// Navigation guards - temporarily disabled for debugging
// router.beforeEach(async (to, _from, next) => {
//   try {
//     const authStore = useAuthStore()
    
//     // Load stored auth if not already loaded
//     if (!authStore.token) {
//       authStore.loadStoredAuth()
//     }
    
//     // Check if route requires authentication
//     if (to.meta.requiresAuth) {
//       if (authStore.isAuthenticated) {
//         next()
//       } else {
//         next('/login')
//       }
//     }
//     // Check if route requires guest (user not logged in)
//     else if (to.meta.requiresGuest) {
//       if (authStore.isAuthenticated) {
//         next('/dashboard')
//       } else {
//         next()
//       }
//     }
//     // Public routes
//     else {
//       next()
//     }
//   } catch (error) {
//     console.error('Router navigation error:', error)
//     next('/login')
//   }
// })

export default router