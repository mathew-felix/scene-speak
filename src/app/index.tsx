import { Redirect } from 'expo-router';

import { useAuth } from '@/contexts/auth-context';

// The first route ("/"). It shows nothing itself; it only sends the user to the
// gallery when signed in, or to the login screen otherwise.
export default function RootIndex() {
  const { isAuthenticated } = useAuth();
  return <Redirect href={isAuthenticated ? '/gallery' : '/login'} />;
}
