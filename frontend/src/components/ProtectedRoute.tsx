// src/presentation/components/ProtectedRoute.tsx
import React, { useEffect } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { AuthService } from '../api/authService';

export const ProtectedRoute: React.FC = () => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const user = useAuthStore((state) => state.user);
  const setUser = useAuthStore((state) => state.setUser);

  // Gọi API verify token ngầm khi component mount
  // MUST be called before any early returns to follow Rules of Hooks
  useEffect(() => {
    if (isAuthenticated) {
      const authService = new AuthService();
      authService.verifyToken().catch(() => {
        // Lỗi 401 sẽ bị interceptor bắt và tự động gọi logout, sau đó isAuthenticated sẽ trigger re-render
      });
      
      // Nếu có token nhưng chưa có thông tin user (do F5 tải lại trang), fetch lại user profile
      if (!user) {
        authService.getCurrentUser()
          .then((profile) => setUser(profile))
          .catch(() => {
             // Lỗi 401 interceptor sẽ xử lý
          });
      }
    }
  }, [isAuthenticated, user, setUser]);

  // Nếu chưa đăng nhập, điều hướng ngay lập tức về trang login
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Nếu đã đăng nhập, cho phép hiển thị các component con (các trang bên trong)
  return <Outlet />;
};