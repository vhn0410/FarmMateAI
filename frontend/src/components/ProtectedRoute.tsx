// src/presentation/components/ProtectedRoute.tsx
import React, { useEffect } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { AuthService } from '../api/authService';

export const ProtectedRoute: React.FC = () => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  // Nếu chưa đăng nhập, điều hướng ngay lập tức về trang login
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Gọi API verify token ngầm khi component mount
  useEffect(() => {
    if (isAuthenticated) {
      const authService = new AuthService();
      authService.verifyToken().catch(() => {
        // Lỗi 401 sẽ bị interceptor bắt và tự động gọi logout, sau đó isAuthenticated sẽ trigger re-render
      });
    }
  }, [isAuthenticated]);

  // Nếu đã đăng nhập, cho phép hiển thị các component con (các trang bên trong)
  return <Outlet />;
};