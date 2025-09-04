<template>
  <Teleport to="body">
    <div class="notification-container">
      <Transition
        v-for="notification in notifications"
        :key="notification.id"
        name="notification"
        appear
      >
        <div
          :class="[
            'notification-toast',
            `notification-${notification.type}`
          ]"
        >
          <div class="notification-icon">
            <svg v-if="notification.type === 'success'" viewBox="0 0 24 24" fill="currentColor">
              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
            </svg>
            <svg v-else-if="notification.type === 'error'" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
            <svg v-else-if="notification.type === 'warning'" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>
            </svg>
          </div>
          
          <div class="notification-content">
            <p class="notification-message">{{ notification.message }}</p>
            <p v-if="notification.description" class="notification-description">
              {{ notification.description }}
            </p>
          </div>
          
          <button @click="removeNotification(notification.id)" class="notification-close">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

export interface NotificationOptions {
  message: string
  description?: string
  type?: 'success' | 'error' | 'warning' | 'info'
  duration?: number
}

interface Notification extends NotificationOptions {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
}

const notifications = ref<Notification[]>([])

const addNotification = (options: NotificationOptions) => {
  const notification: Notification = {
    id: Math.random().toString(36).substr(2, 9),
    type: 'info',
    duration: 5000,
    ...options
  }
  
  notifications.value.push(notification)
  
  if (notification.duration && notification.duration > 0) {
    setTimeout(() => {
      removeNotification(notification.id)
    }, notification.duration)
  }
}

const removeNotification = (id: string) => {
  const index = notifications.value.findIndex(n => n.id === id)
  if (index > -1) {
    notifications.value.splice(index, 1)
  }
}

// Função global para adicionar notificações
const showNotification = (message: string, type: 'success' | 'error' | 'warning' | 'info' = 'info', description?: string) => {
  addNotification({ message, type, description })
}

// Expor função globalmente
onMounted(() => {
  window.showNotification = showNotification
})

// Expor métodos para uso direto
defineExpose({
  addNotification,
  removeNotification,
  showNotification
})
</script>

<style scoped>
.notification-container {
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-width: 400px;
}

.notification-toast {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 1rem;
  border-radius: 8px;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
  background: white;
  border-left: 4px solid #d1d5db;
  min-width: 320px;
}

.notification-success {
  border-left-color: #374151;
  background: #f9fafb;
}

.notification-error {
  border-left-color: #6b7280;
  background: #f9fafb;
}

.notification-warning {
  border-left-color: #9ca3af;
  background: #f9fafb;
}

.notification-info {
  border-left-color: #1f2937;
  background: #f9fafb;
}

.notification-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.25rem;
  height: 1.25rem;
  flex-shrink: 0;
  margin-top: 0.125rem;
}

.notification-success .notification-icon {
  color: #374151;
}

.notification-error .notification-icon {
  color: #6b7280;
}

.notification-warning .notification-icon {
  color: #9ca3af;
}

.notification-info .notification-icon {
  color: #1f2937;
}

.notification-icon svg {
  width: 100%;
  height: 100%;
}

.notification-content {
  flex: 1;
}

.notification-message {
  font-weight: 500;
  color: #1f2937;
  margin: 0 0 0.25rem;
  line-height: 1.4;
}

.notification-description {
  font-size: 0.875rem;
  color: #6b7280;
  margin: 0;
  line-height: 1.4;
}

.notification-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.25rem;
  height: 1.25rem;
  border: none;
  background: none;
  color: #9ca3af;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s;
  flex-shrink: 0;
}

.notification-close:hover {
  color: #6b7280;
  background: rgba(0, 0, 0, 0.05);
}

.notification-close svg {
  width: 100%;
  height: 100%;
}

/* Animações */
.notification-enter-active,
.notification-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.notification-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.notification-leave-to {
  opacity: 0;
  transform: translateX(100%);
}

.notification-enter-to,
.notification-leave-from {
  opacity: 1;
  transform: translateX(0);
}

/* Responsivo */
@media (max-width: 640px) {
  .notification-container {
    left: 1rem;
    right: 1rem;
    max-width: none;
  }
  
  .notification-toast {
    min-width: auto;
  }
}
</style>