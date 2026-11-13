import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import * as authApi from '../api/auth.js';

const AuthContext = createContext(null);
const TOKEN_KEY = 'nutriscan_token';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const saveSession = useCallback((data) => {
    window.sessionStorage.setItem(TOKEN_KEY, data.token);
    setUser(data.user);
  }, []);

  const signIn = useCallback(async (credentials) => {
    const { data } = await authApi.login(credentials);
    saveSession(data);
    return data.user;
  }, [saveSession]);

  const signUp = useCallback(async (details) => {
    const { data } = await authApi.register(details);
    saveSession(data);
    return data.user;
  }, [saveSession]);

  const signOut = useCallback(() => {
    window.sessionStorage.removeItem(TOKEN_KEY);
    setUser(null);
  }, []);

  useEffect(() => {
    let active = true;
    if (!window.sessionStorage.getItem(TOKEN_KEY)) {
      setLoading(false);
      return () => {
        active = false;
      };
    }

    authApi.getCurrentUser()
      .then(({ data }) => {
        if (active) setUser(data.user);
      })
      .catch(() => {
        window.sessionStorage.removeItem(TOKEN_KEY);
        if (active) setUser(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => signOut();
    window.addEventListener('nutriscan:unauthorized', handleUnauthorized);
    return () => {
      window.removeEventListener('nutriscan:unauthorized', handleUnauthorized);
    };
  }, [signOut]);

  const value = useMemo(
    () => ({
      user,
      loading,
      isAuthenticated: Boolean(user),
      signIn,
      signUp,
      signOut,
    }),
    [user, loading, signIn, signUp, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside an AuthProvider.');
  return context;
}
