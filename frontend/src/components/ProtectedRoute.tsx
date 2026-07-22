// src/presentation/components/ProtectedRoute.tsx
import React, { useEffect } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { AuthService } from '../api/authService';

interface ProtectedRouteProps {
  requireAdmin?: boolean;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ requireAdmin = false }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const user = useAuthStore((state) => state.user);
  const setUser = useAuthStore((state) => state.setUser);

  // Call the token verification API silently when the component mounts
  // MUST be called before any early returns to follow Rules of Hooks
  useEffect(() => {
    if (isAuthenticated) {
      const authService = new AuthService();
      authService.verifyToken().catch(() => {
        // 401 errors will be caught by the interceptor and trigger logout, which will cause isAuthenticated to re-render
      });
      
      // If there is a token but no user yet (for example after a hard refresh), fetch the user profile again
      if (!user) {
        authService.getCurrentUser()
          .then((profile) => setUser(profile))
          .catch(() => {
             // The 401 interceptor will handle any error
          });
      }
    }
  }, [isAuthenticated, user, setUser]);

  // If the user is not logged in, redirect immediately to the login page
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // If admin access is required but the user is still loading or is not an admin
  if (requireAdmin) {
    if (!user) {
      // The user profile is still loading; show a loading state here
      return <div>Loading...</div>; 
    }
    if (user.role !== 'admin') {
      return <Navigate to="/chat" replace />;
    }
  }

  // If the user is authenticated, allow the child components to render
  return <Outlet />;
};