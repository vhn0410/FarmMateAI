// src/presentation/routes.tsx
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { ProtectedRoute } from './components/ProtectedRoute';
import { LoginPage } from './pages/LoginPage'; // <--- Import component thật

// Mock tạm ChatPage để chờ bước sau ráp reachat.dev
const ChatPageMock = () => (
  <div className="flex h-screen items-center justify-center bg-white text-2xl font-bold text-gray-700">
    Đăng nhập thành công! Đây sẽ là nơi chứa Reachat.dev
  </div>
);

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />, // <--- Đưa component thật vào đây
  },
  {
    element: <ProtectedRoute />, 
    children: [
      {
        path: '/chat',
        element: <ChatPageMock />,
      },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/chat" replace />,
  },
]);