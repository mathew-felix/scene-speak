import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

import { isValidStaticLogin } from '@/lib/static-login';

type AuthContextValue = {
  isAuthenticated: boolean;
  signIn: (email: string, password: string) => boolean;
  signOut: () => void;
};

// React "context": a way to share the login state with any screen without passing it
// down by hand. `null` means no provider is wrapping the component.
const AuthContext = createContext<AuthContextValue | null>(null);

// Wrap the app in this once (see app/_layout.tsx). The login lives in memory only,
// so the user signs in again each time the app is started.
export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const signIn = useCallback((email: string, password: string) => {
    const ok = isValidStaticLogin(email, password);
    setIsAuthenticated(ok);
    return ok;
  }, []);
  const signOut = useCallback(() => setIsAuthenticated(false), []);

  const value = useMemo(() => ({ isAuthenticated, signIn, signOut }), [isAuthenticated, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// Use this in any screen to read `isAuthenticated` or call `signIn` / `signOut`.
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
}
