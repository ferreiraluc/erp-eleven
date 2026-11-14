import { Capacitor, registerPlugin } from '@capacitor/core'

const settings = registerPlugin<{
  prepareChannel(): Promise<{ channelId: string }>
  status(): Promise<{ enabled: boolean }>
  open(): Promise<void>
}>('ElevenNotificationSettings')

export const ANDROID_NOTIFICATION_CHANNEL_ID = 'eleven-updates-v2' as const

export const canOpenNativeNotificationSettings = () =>
  Capacitor.isNativePlatform() && Capacitor.getPlatform() === 'android'

export async function prepareNativeNotificationChannel(): Promise<void> {
  if (!canOpenNativeNotificationSettings()) return
  const result = await settings.prepareChannel()
  if (result.channelId !== ANDROID_NOTIFICATION_CHANNEL_ID) throw new Error('notification-channel-unavailable')
}

export async function nativeNotificationsAllowed(): Promise<boolean> {
  if (!canOpenNativeNotificationSettings()) return true
  return (await settings.status()).enabled === true
}

export async function openNativeNotificationSettings(): Promise<void> {
  if (!canOpenNativeNotificationSettings()) throw new Error('settings-unavailable')
  await settings.open()
}
