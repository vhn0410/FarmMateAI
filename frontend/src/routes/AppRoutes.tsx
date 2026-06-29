// src/presentation/routes.tsx
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { Layout } from '../components/Layout';
import { LoginPage } from '../pages/auth/Login'; 
import { ChatWorkspace } from '../pages/dashboard/chat/ChatWorkspace';
import { KnowledgeWorkspace } from '../pages/dashboard/knowledge/KnowledgeWorkspace';


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
          {
            path: '/knowledge',
            element: <KnowledgeWorkspace />,
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