import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

import { isValidStaticLogin } from '@/lib/static-login';

type AuthContextValue = {
  isAuthenticated: boolean;
  signIn: (email: string, password: string) => boolean;
  signOut: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

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

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
}
