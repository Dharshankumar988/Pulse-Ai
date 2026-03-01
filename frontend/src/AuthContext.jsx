import { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('pulseToken') || '');
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('pulseUser')); } catch { return null; }
  });

  useEffect(() => {
    if (token) localStorage.setItem('pulseToken', token);
    else localStorage.removeItem('pulseToken');
  }, [token]);

  useEffect(() => {
    if (user) localStorage.setItem('pulseUser', JSON.stringify(user));
    else localStorage.removeItem('pulseUser');
  }, [user]);

  const login = (accessToken, userData) => {
    setToken(accessToken);
    setUser(userData);
  };

  const logout = () => {
    setToken('');
    setUser(null);
  };

  const isLoggedIn = Boolean(token && user);
  const isAdmin = user?.role === 'admin';

  return (
    <AuthContext.Provider value={{ token, user, isLoggedIn, isAdmin, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
