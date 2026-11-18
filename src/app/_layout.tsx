import { DarkTheme, Stack, ThemeProvider } from 'expo-router';

import { StatusBar } from 'expo-status-bar';

import { Colors } from '@/constants/theme';
import { AuthProvider } from '@/contexts/auth-context';

const theme = {
  ...DarkTheme,
  colors: { ...DarkTheme.colors, background: Colors.dark.background, card: Colors.dark.background, primary: Colors.dark.accent },
};

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
