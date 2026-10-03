/**
 * Authentication context and hook.
 * Provides auth state and actions throughout the app.
 */
import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { User, AuthTokens, AuthState } from '../types';
import apiClient from '../lib/api';
import authService from '../services/authService';

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
    role: 'CUSTOMER' | 'KITCHEN_OWNER' | 'ADMIN';
  }) => Promise<string>;
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
   * On mount, check if we have stored tokens and fetch user.
   */
  useEffect(() => {
    const initAuth = async () => {
      if (apiClient.isAuthenticated()) {
        try {
          const user = await authService.getMe();
          setState({
            user,
            tokens: {
              access_token: apiClient.getAccessToken()!,
              refresh_token: '',
              token_type: 'bearer',
              expires_in: 0,
            },
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
        } catch {
          // Token invalid, clear it
          apiClient.clearTokens();
          setState(prev => ({ ...prev, isLoading: false }));
        }
      } else {
        setState(prev => ({ ...prev, isLoading: false }));
      }
    };

    initAuth();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));
    try {
      const tokens = await authService.login(email, password);
      apiClient.setTokens(tokens.access_token, tokens.refresh_token);
      
      const user = await authService.getMe();
      
      setState({
        user,
        tokens,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (err: any) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: err.detail || err.message || 'Login failed',
      }));
      throw err;
    }
  }, []);

  const register = useCallback(async (data: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
    role: 'CUSTOMER' | 'KITCHEN_OWNER' | 'ADMIN';
  }) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));
    try {
      const response = await authService.register(data);
      setState(prev => ({ ...prev, isLoading: false }));
      return response.message;
    } catch (err: any) {
      const message = err.errors?.join(', ') || err.detail || err.message || 'Registration failed';
      setState(prev => ({ ...prev, isLoading: false, error: message }));
      throw err;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } catch {
      // Ignore logout errors
    } finally {
      apiClient.clearTokens();
      setState({
        user: null,
        tokens: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    }
  }, []);

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
