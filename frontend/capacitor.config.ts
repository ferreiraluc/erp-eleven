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
  plugins: {
    // One inset owner: Capacitor fits the viewport around bars, cutouts and the
    // keyboard. Match the viewport-fit=contain metadata in build-mobile.mjs.
    SystemBars: { insetsHandling: 'native', initialViewportFitValueHint: 'contain', style: 'LIGHT' },
  },
}
export default config
