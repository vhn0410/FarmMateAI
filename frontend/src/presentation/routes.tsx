// src/presentation/routes.tsx
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { ProtectedRoute } from './components/ProtectedRoute';
import { LoginPage } from './pages/LoginPage'; // <--- Import component thật
import { ChatPage } from './pages/ChatPage';


export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />, 
  },
  {
    element: <ProtectedRoute />, 
    children: [
      {
        path: '/chat',
        element: <ChatPage />,
      },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/chat" replace />,
  },
]);