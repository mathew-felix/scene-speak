import { Redirect, Stack } from 'expo-router';

import { Colors } from '@/constants/theme';
import { useAuth } from '@/contexts/auth-context';

// Guard for every screen inside the (main) folder (gallery and player).
// The folder name in parentheses is a route group: it organizes files without
// adding anything to the URL. Signed-out users are sent to the login screen.
export default function MainLayout() {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Redirect href="/login" />;
  }
  return <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: Colors.dark.background } }} />;
}
