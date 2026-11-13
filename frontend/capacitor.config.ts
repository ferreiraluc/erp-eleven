import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'com.elevenparispy.erp',
  appName: 'Eleven',
  webDir: 'dist-mobile',
  backgroundColor: '#f8fafc',
  loggingBehavior: 'debug',
  server: {
    hostname: 'localhost',
    androidScheme: 'https',
    iosScheme: 'capacitor',
    cleartext: false,
  },
  android: { allowMixedContent: false, webContentsDebuggingEnabled: false },
  ios: { contentInset: 'automatic', preferredContentMode: 'mobile', webContentsDebuggingEnabled: false },
}
export default config
