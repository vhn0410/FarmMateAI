// src/presentation/pages/LoginPage.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthActions } from '../../application/hooks/useAuthActions';

export const LoginPage: React.FC = () => {
  // Quản lý state của form
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  
  // Lấy các hàm và state từ Custom Hook
  const { handleLogin, isLoading, error } = useAuthActions();
  const navigate = useNavigate();

  // Xử lý sự kiện submit form
  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); // Ngăn chặn hành vi reload trang mặc định của form
    
    if (!username || !password) return;

    // Gọi action login
    const isSuccess = await handleLogin({ username, password });
    
    // Nếu API trả về thành công và lưu token/state xong, chuyển hướng sang trang Chat
    if (isSuccess) {
      navigate('/chat', { replace: true });
    }
  };

  return (
    <div className="flex h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-md rounded-xl bg-white p-8 shadow-lg">
        {/* Header trang Login */}
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-green-600">FarmMate AI</h1>
          <p className="mt-2 text-sm text-gray-500">
            Hệ thống trợ lý ảo Nông nghiệp thông minh
          </p>
        </div>

        {/* Khối hiển thị lỗi nếu có */}
        {error && (
          <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-600 border border-red-200">
            {error}
          </div>
        )}

        {/* Form đăng nhập */}
        <form onSubmit={onSubmit} className="space-y-5">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="username">
              Tên đăng nhập
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={isLoading}
              className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500 disabled:bg-gray-100"
              placeholder="Nhập tài khoản của bạn"
              required
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="password">
              Mật khẩu
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isLoading}
              className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500 disabled:bg-gray-100"
              placeholder="••••••••"
              required
            />
          </div>

          <button
            type="submit"
            disabled={isLoading || !username || !password}
            className="w-full rounded-lg bg-green-600 px-4 py-2.5 font-medium text-white transition-colors hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-green-400 flex justify-center items-center"
          >
            {isLoading ? (
              <span className="flex items-center gap-2">
                <svg className="h-5 w-5 animate-spin text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Đang xử lý...
              </span>
            ) : (
              'Đăng nhập'
            )}
          </button>
        </form>
      </div>
    </div>
  );
};