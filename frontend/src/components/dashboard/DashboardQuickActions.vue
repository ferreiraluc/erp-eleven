<template>
  <nav
    class="quick-strip"
    :class="{ 'quick-strip--primary': primaryOnly }"
    :aria-label="uiText('Ações Rápidas')"
  >
    <button
      v-for="action in visibleActions"
      :key="action.path"
      type="button"
      class="quick-btn erp-control"
      :class="[action.color, { 'quick-btn--primary': primaryPaths.includes(action.path) }]"
      @click="router.push(action.path)"
    >
      <span class="quick-btn-icon" aria-hidden="true">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            v-for="path in action.icon"
            :key="path"
            :d="path"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
          />
        </svg>
      </span>
      <span>{{ uiText(action.label) }}</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { uiText } from '@/i18n/uiText'

const props = defineProps<{ primaryOnly?: boolean }>()
const router = useRouter()
const authStore = useAuthStore()
const primaryPaths = ['/pdv', '/vendas-pdv', '/inventory', '/clientes']

const actions = [
  {
    label: 'Nova Venda',
    color: 'q-primary',
    path: '/pdv',
    icon: ['M12 6v6m0 0v6m0-6h6m-6 0H6'],
    access: 'all',
  },
  {
    label: 'Vendas',
    color: 'q-primary',
    path: '/vendas-pdv',
    icon: ['M8 3h8l4 4v14l-4-2-4 2-4-2-4 2V3h4zm0 6h8m-8 4h8'],
    access: 'all',
  },
  {
    label: 'Estoque',
    color: 'q-orange',
    path: '/inventory',
    icon: ['M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4'],
    access: 'all',
  },
  {
    label: 'Vendedores',
    color: 'q-green',
    path: '/vendors',
    icon: [
      'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z',
    ],
    access: 'all',
  },
  {
    label: 'Pedidos',
    color: 'q-purple',
    path: '/pedidos',
    icon: ['M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z'],
    access: 'all',
  },
  {
    label: 'Rastreamento',
    color: 'q-teal',
    path: '/rastreamento',
    icon: [
      'M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z',
      'M15 11a3 3 0 11-6 0 3 3 0 016 0z',
    ],
    access: 'all',
  },
  {
    label: 'Clientes',
    color: 'q-indigo',
    path: '/clientes',
    icon: [
      'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z',
    ],
    access: 'all',
  },
  {
    label: 'Pagadores',
    color: 'q-amber',
    path: '/fiado',
    icon: [
      'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253',
    ],
    access: 'all-sales',
  },
  {
    label: 'Assistente IA',
    color: 'q-indigo',
    path: '/assistente',
    icon: ['M8 10h8M8 14h5M5 4h14a2 2 0 012 2v12a2 2 0 01-2 2H9l-5 2V6a2 2 0 012-2z'],
    access: 'admin',
  },
  {
    label: 'Endereços e envios',
    color: 'q-teal',
    path: '/enderecos',
    icon: ['M21 10c0 7-9 12-9 12S3 17 3 10a9 9 0 1118 0Z', 'M15 10a3 3 0 11-6 0 3 3 0 016 0Z'],
    access: 'manager',
  },
]
const visibleActions = computed(() =>
  actions
    .filter((action) => {
      if (props.primaryOnly && !primaryPaths.includes(action.path)) return false
      if (action.access === 'manager')
        return ['ADMIN', 'GERENTE'].includes(authStore.user?.role || '')
      if (action.access === 'admin') return authStore.user?.role === 'ADMIN'
      if (action.access === 'all-sales') return !authStore.ownSales
      return true
    })
    .sort((a, b) =>
      props.primaryOnly ? primaryPaths.indexOf(a.path) - primaryPaths.indexOf(b.path) : 0,
    ),
)
</script>

<style scoped>
.quick-strip {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 0.5rem;
}

.quick-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.625rem 0.375rem;
  border: none;
  border-radius: 0.625rem;
  cursor: pointer;
  gap: 0.375rem;
  transition: all 0.15s;
  font-size: 0.72rem;
  font-weight: 600;
  line-height: 1.2;
}
.quick-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
}

.quick-btn-icon {
  width: 2.125rem;
  height: 2.125rem;
  background: rgba(0, 0, 0, 0.07);
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
}
.quick-btn-icon svg {
  width: 1.1rem;
  height: 1.1rem;
  stroke: currentColor;
}

.q-primary {
  background: #eff6ff;
  color: #2563eb;
}
.q-primary:hover {
  background: #dbeafe;
}
.q-orange {
  background: #fff7ed;
  color: #ea580c;
}
.q-orange:hover {
  background: #fed7aa;
}
.q-green {
  background: #f0fdf4;
  color: #16a34a;
}
.q-green:hover {
  background: #dcfce7;
}
.q-purple {
  background: #faf5ff;
  color: #9333ea;
}
.q-purple:hover {
  background: #f3e8ff;
}
.q-teal {
  background: #f0fdfa;
  color: #0d9488;
}
.q-teal:hover {
  background: #ccfbf1;
}
.q-indigo {
  background: #eef2ff;
  color: #4338ca;
}
.q-indigo:hover {
  background: #e0e7ff;
}
.q-amber {
  background: #fffbeb;
  color: #d97706;
}
.q-amber:hover {
  background: #fef3c7;
}

.quick-btn {
  min-width: 0;
  justify-content: center;
  text-align: center;
}
.quick-btn:focus-visible {
  outline: 2px solid currentColor;
  outline-offset: 3px;
}
.quick-strip--primary {
  display: none;
}

/* Include iPad Pro in landscape without changing desktop pointer layouts. */
@media (max-width: 1024px), (max-width: 1366px) and (hover: none) and (pointer: coarse) {
  .quick-strip {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .quick-strip:not(.quick-strip--primary) .quick-btn--primary {
    display: none;
  }
  .quick-strip--primary {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  .quick-strip--primary .quick-btn {
    min-height: 5rem;
  }
}
</style>
