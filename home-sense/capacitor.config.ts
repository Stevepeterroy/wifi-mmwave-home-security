import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'app.haven.homesense',
  appName: 'Haven',
  webDir: 'dist',
  android: {
    allowMixedContent: true,
  },
  server: {
    // During development you can set a live reload URL here.
    // For production APK this is left empty so the app loads from bundled assets.
    cleartext: true,
  },
};

export default config;
