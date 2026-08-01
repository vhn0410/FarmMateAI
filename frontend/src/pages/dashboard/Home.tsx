import React from 'react';
import { Link } from 'react-router-dom';

export const Home: React.FC = () => {
  return (
    <div className="flex flex-col items-center justify-center h-screen bg-gray-50">
      <h1 className="text-3xl font-bold text-teal-700 mb-6">Welcome to FarmMate AI</h1>
      <p className="text-gray-600 mb-8">Your intelligent agricultural assistant.</p>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Link to="/chat" className="p-6 bg-white rounded-lg shadow hover:shadow-md transition">
          <h2 className="text-xl font-semibold mb-2">💬 AI Chatbot</h2>
          <p className="text-gray-500">Ask questions and get expert agricultural advice.</p>
        </Link>
        <div className="p-6 bg-white rounded-lg shadow opacity-60 cursor-not-allowed">
          <h2 className="text-xl font-semibold mb-2">📚 Knowledge Base</h2>
          <p className="text-gray-500">Manage and sync documents (Coming soon).</p>
        </div>
      </div>
    </div>
  );
};
