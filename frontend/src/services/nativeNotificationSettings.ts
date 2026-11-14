import { Capacitor, registerPlugin } from '@capacitor/core'

const settings = registerPlugin<{
  status(): Promise<{ enabled: boolean }>
  open(): Promise<void>
}>('ElevenNotificationSettings')

export const canOpenNativeNotificationSettings = () =>
  Capacitor.isNativePlatform() && Capacitor.getPlatform() === 'android'

export async function nativeNotificationsAllowed(): Promise<boolean> {
  if (!canOpenNativeNotificationSettings()) return true
  return (await settings.status()).enabled === true
}

export async function openNativeNotificationSettings(): Promise<void> {
  if (!canOpenNativeNotificationSettings()) throw new Error('settings-unavailable')
  await settings.open()
}
