// src/application/hooks/useAuthActions.ts
import { useState } from 'react';
import { AuthService } from '../../infrastructure/services/AuthService';
import { useAuthStore } from '../store/useAuthStore';
import type { LoginRequest } from '../../domain/models/Auth';

const authService = new AuthService();

export const useAuthActions = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const setAuth = useAuthStore((state) => state.setAuth);

  const handleLogin = async (credentials: LoginRequest): Promise<boolean> => {
    setIsLoading(true);
    setError(null);
    try {
      // 1. Gọi API Login lấy Token
      const tokenData = await authService.login(credentials);
      
      // Lưu tạm token vào localStorage để axios interceptor kịp đính kèm vào header cho request kế tiếp
      localStorage.setItem('access_token', tokenData.access_token);
      
      // 2. Gọi API lấy thông tin Profile để JIT sync dữ liệu
      const profile = await authService.getCurrentUser();
      
      // 3. Đồng bộ vào Zustand global state
      setAuth(tokenData.access_token, profile);
      return true;
    } catch (err: any) {
      localStorage.removeItem('access_token');
      setError(err.response?.data?.detail?.[0]?.msg || 'Đăng nhập thất bại. Vui lòng thử lại.');
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  return { handleLogin, isLoading, error };
};