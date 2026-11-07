import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { User, AuthTokens, AuthState, RegisterRequest } from '../types';
import apiClient from '../lib/api';
import authService from '../services/authService';

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<User>;
  register: (data: RegisterRequest) => Promise<string>;
  logout: () => Promise<void>;
  fetchUser: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    tokens: null,
    isAuthenticated: false,
    isLoading: true,
    error: null,
  });

  /**
   * On mount, check if we have stored tokens or active session and fetch authoritative user.
   */
  useEffect(() => {
    let isMounted = true;

    const initAuth = async () => {
      try {
        if (apiClient.isAuthenticated()) {
          const user = await authService.getMe();
          if (isMounted) {
            const token = (user as any).access_token || apiClient.getAccessToken()!;
            if (token && token !== 'cookie-session') {
              apiClient.setTokens(token, '', user.role);
            }
            setState({
              user,
              tokens: {
                access_token: token,
                refresh_token: '',
                token_type: 'bearer',
                expires_in: 0,
              },
              isAuthenticated: true,
              isLoading: false,
              error: null,
            });
          }
          return;
        }

        // Check if HttpOnly cookie session exists on the backend
        try {
          const user = await authService.getMe();
          if (user && isMounted) {
            const token = (user as any).access_token || '';
            if (token && token !== 'cookie-session') {
              apiClient.setTokens(token, '', user.role);
            }
            setState({
              user,
              tokens: {
                access_token: token || '',
                refresh_token: '',
                token_type: 'bearer',
                expires_in: 0,
              },
              isAuthenticated: true,
              isLoading: false,
              error: null,
            });
            return;
          }
        } catch {
          // No active session cookie
        }
      } catch {
        apiClient.clearTokens();
      }

      if (isMounted) {
        setState({
          user: null,
          tokens: null,
          isAuthenticated: false,
          isLoading: false,
          error: null,
        });
      }
    };

    initAuth();
    return () => {
      isMounted = false;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));
    try {
      const resp: any = await authService.login(email, password);
      const accessToken = resp.access_token;
      const refreshToken = resp.refresh_token;
      const role = resp.role;
      if (accessToken) {
        apiClient.setTokens(accessToken, refreshToken || '', role);
      }
      
      const user = await authService.getMe();
      if (user?.role && accessToken) {
        apiClient.setTokens(accessToken, refreshToken || '', user.role);
      }
      
      setState({
        user,
        tokens: {
          access_token: accessToken || '',
          refresh_token: refreshToken || '',
          token_type: 'bearer',
          expires_in: 86400,
        },
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
      return user;
    } catch (err: any) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: err.detail || err.message || 'Login failed',
      }));
      throw err;
    }
  }, []);

  const register = useCallback(async (data: RegisterRequest) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));
    try {
      const response = await authService.register(data);
      setState(prev => ({ ...prev, isLoading: false }));
      return response.message;
    } catch (err: any) {
      const message = (Array.isArray(err.errors) && err.errors.length > 0)
        ? err.errors.join(', ')
        : (err.detail || err.message || 'Registration failed');
      setState(prev => ({ ...prev, isLoading: false, error: message }));
      throw err;
    }
  }, []);

  const logout = useCallback(async () => {
    const currentRole = state.user?.role;
    try {
      await authService.logout();
    } catch {
      // Ignore logout errors
    } finally {
      apiClient.clearTokens(currentRole);
      setState({
        user: null,
        tokens: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    }
  }, [state.user?.role]);

  const fetchUser = useCallback(async () => {
    try {
      const user = await authService.getMe();
      setState(prev => ({ ...prev, user }));
    } catch {
      // If fetch fails, user might be logged out
    }
  }, []);

  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null }));
  }, []);

  return (
    <AuthContext.Provider value={{
      ...state,
      login,
      register,
      logout,
      fetchUser,
      clearError,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Hook to access authentication state and actions.
 */
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default AuthContext;
