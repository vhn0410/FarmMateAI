// src/presentation/routes.tsx
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { Layout } from '../components/Layout';
import { LoginPage } from '../pages/auth/Login'; 
import { ChatWorkspace } from '../pages/dashboard/chat/ChatWorkspace';


export const router = createBrowserRouter([
  {
    path: '/',
    element: <Navigate to="/login" replace />,
  },
  {
    path: '/login',
    element: <LoginPage />, 
  },
  {
    element: <ProtectedRoute />, 
    children: [
      {
        element: <Layout />,
        children: [
          {
            path: '/chat',
            element: <ChatWorkspace />,
          },
        ]
      }
    ],
  },
  {
    path: '*',
    element: <Navigate to="/chat" replace />,
  },
]);