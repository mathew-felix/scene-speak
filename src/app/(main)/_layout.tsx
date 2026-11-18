import { Redirect, Stack } from 'expo-router';

import { Colors } from '@/constants/theme';
import { useAuth } from '@/contexts/auth-context';

export default function MainLayout() {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Redirect href="/login" />;
  }
  return <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: Colors.dark.background } }} />;
}
