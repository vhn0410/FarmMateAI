// src/application/hooks/useAuthActions.ts
import { useState } from 'react';
import { AuthService } from '../api/authService';
import { useAuthStore } from '../store/useAuthStore';
import type { LoginRequest } from '../models/Auth';

const authService = new AuthService();

export const useAuthActions = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const setAuth = useAuthStore((state) => state.setAuth);

  const handleLogin = async (credentials: LoginRequest): Promise<boolean> => {
    setIsLoading(true);
    setError(null);
    try {
      // 1. Call the login API to obtain a token
      const tokenData = await authService.login(credentials);
      
      // Store the token temporarily in localStorage so the axios interceptor can attach it to the next request
      localStorage.setItem('access_token', tokenData.access_token);
      
      // 2. Call the profile API to sync user data lazily
      const profile = await authService.getCurrentUser();
      
      // 3. Sync the data into the global Zustand state
      setAuth(tokenData.access_token, profile);
      return true;
    } catch (err: any) {
      localStorage.removeItem('access_token');
      setError(err.response?.data?.detail?.[0]?.msg || 'Login failed. Please try again.');
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  return { handleLogin, isLoading, error };
};