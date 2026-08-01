// src/presentation/pages/LoginPage.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthActions } from '../../hooks/useAuthActions';

export const LoginPage: React.FC = () => {
  // Manage form state
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  
  // Get the functions and state from the custom hook
  const { handleLogin, isLoading, error } = useAuthActions();
  const navigate = useNavigate();

  // Handle the form submit event
  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); // Prevent the browser's default form reload behavior
    
    if (!username || !password) return;

    // Call the login action
    const isSuccess = await handleLogin({ username, password });
    
    // If the API succeeds and the token/state have been saved, navigate to the chat page
    if (isSuccess) {
      navigate('/chat', { replace: true });
    }
  };

  return (
    <div className="flex h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-md rounded-xl bg-white p-8 shadow-sm border border-gray-100">
        {/* Login Header */}
        <div className="mb-10 flex flex-col items-center">
          <img
            src="/farmmate-logo.svg"
            alt="FarmMate AI logo"
            className="h-20 w-auto object-contain drop-shadow-md mb-2"
          />
          <p className="mt-2 text-sm text-gray-500 font-medium tracking-wide">
            Intelligent Agricultural Assistant
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-600 border border-red-200">
            {error}
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={onSubmit} className="space-y-5">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="username">
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={isLoading}
              className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-2 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-100 transition-all disabled:bg-gray-100"
              placeholder="Enter your username"
              required
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isLoading}
              className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-2 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-100 transition-all disabled:bg-gray-100"
              placeholder="••••••••"
              required
            />
          </div>

          <button
            type="submit"
            disabled={isLoading || !username || !password}
            className="w-full rounded-lg bg-teal-600 px-4 py-2.5 font-medium text-white transition-colors hover:bg-teal-700 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-teal-400 flex justify-center items-center shadow-sm"
          >
            {isLoading ? (
              <span className="flex items-center gap-2">
                <svg className="h-5 w-5 animate-spin text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Processing...
              </span>
            ) : (
              'Sign In'
            )}
          </button>
        </form>
      </div>
    </div>
  );
};