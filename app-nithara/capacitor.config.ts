import type { CapacitorConfig } from '@capacitor/cli'

// One codebase → Play Store / App Store. `npm run build` emits dist/, which
// Capacitor packages as the native webDir. Android/iOS platforms are added with
// `npx cap add android|ios` in Part 9.
const config: CapacitorConfig = {
  appId: 'app.nithara',
  appName: 'Nithara',
  webDir: 'dist',
}

export default config
