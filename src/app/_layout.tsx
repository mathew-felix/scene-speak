// Root of the app: sets up the dark theme, status bar and login state for all screens.
import { DarkTheme, Stack, ThemeProvider } from 'expo-router';

import { StatusBar } from 'expo-status-bar';

import { Colors } from '@/constants/theme';
import { AuthProvider } from '@/contexts/auth-context';

// Navigation theme: start from React Navigation's dark theme and swap in our own
// background and accent colors, so screens never flash white during transitions.
const theme = {
  ...DarkTheme,
  colors: { ...DarkTheme.colors, background: Colors.dark.background, card: Colors.dark.background, primary: Colors.dark.accent },
};

// Root layout. Wraps every screen with the theme and the login state (AuthProvider).
// `Stack` shows one screen at a time; headers are hidden because each screen draws its own.
export default function RootLayout() {
  return (
    <ThemeProvider value={theme}>
      <StatusBar style="light" />
      <AuthProvider>
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: Colors.dark.background } }} />
      </AuthProvider>
    </ThemeProvider>
  );
}
