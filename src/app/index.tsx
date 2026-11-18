import { Redirect } from 'expo-router';

import { useAuth } from '@/contexts/auth-context';

export default function RootIndex() {
  const { isAuthenticated } = useAuth();
  return <Redirect href={isAuthenticated ? '/gallery' : '/login'} />;
}
