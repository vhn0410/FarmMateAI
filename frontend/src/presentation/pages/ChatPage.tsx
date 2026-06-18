// src/presentation/pages/ChatPage.tsx
import React, { useState, useRef, useEffect } from 'react';
import { useChatbot } from '../../application/hooks/useChatbot';
import { useAuthStore } from '../../application/store/useAuthStore';

export const ChatPage: React.FC = () => {
  const { messages, isLoading, sendMessage } = useChatbot();
  const user = useAuthStore(state => state.user);
  const [input, setInput] = useState('');

  // Ref dùng để tự động cuộn xuống tin nhắn mới nhất
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    sendMessage(input);
    setInput('');
  };

  return (
    <div className="flex h-screen flex-col bg-gray-50 font-sans">
      {/* HEADER */}
      <header className="flex h-16 shrink-0 items-center justify-between bg-white px-6 shadow-sm border-b border-gray-200 z-10">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-green-600 text-white font-bold shadow-md">
            FM
          </div>
          <h1 className="text-xl font-bold text-gray-800 tracking-tight">FarmMate AI Agent</h1>
        </div>
        <div className="text-sm text-gray-600 flex items-center gap-2 bg-gray-100 px-3 py-1.5 rounded-full">
          <span className="h-2.5 w-2.5 rounded-full bg-green-500 animate-pulse"></span>
          <span className="font-medium">{user?.full_name || user?.username}</span>
        </div>
      </header>

      {/* MESSAGE LIST */}
      <main className="flex-1 overflow-y-auto p-4 sm:p-6 scroll-smooth">
        <div className="mx-auto max-w-4xl space-y-6">
          {/* Lời chào mặc định */}
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center text-center mt-20 text-gray-500 space-y-4">
              <div className="h-16 w-16 bg-green-100 rounded-full flex items-center justify-center mb-2">
                <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path></svg>
              </div>
              <h2 className="text-2xl font-semibold text-gray-700">Hôm nay nông trại của bạn thế nào?</h2>
              <p>Hãy hỏi FarmMate bất kỳ câu hỏi nào về kỹ thuật nông nghiệp.</p>
            </div>
          )}

          {/* Vòng lặp render tin nhắn */}
          {messages.map((msg) => (
            <div key={msg.id} className={`flex items-start ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {/* Avatar Bot */}
              {msg.role === 'bot' && (
                <div className="mr-3 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-green-600 text-white font-bold shadow-sm mt-1">
                  FM
                </div>
              )}

              <div className="max-w-[85%] sm:max-w-[75%] flex flex-col gap-2">

                {/* 1. KHU VỰC HIỂN THỊ QUÁ TRÌNH SUY NGHĨ CỦA AI */}
                {msg.role === 'bot' && msg.statuses && msg.statuses.length > 0 && (
                  <div className="bg-gray-50 border border-gray-200 rounded-xl p-3.5 text-sm shadow-sm transition-all">
                    <div className="flex items-center gap-2 mb-2 font-semibold text-gray-700">
                      {isLoading && messages[messages.length - 1].id === msg.id ? (
                        <svg className="w-4 h-4 animate-spin text-green-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                      ) : (
                        <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7"></path></svg>
                      )}
                      Quá trình AI xử lý:
                    </div>
                    <ul className="space-y-1 ml-6 list-disc marker:text-gray-300 text-gray-600 font-mono text-xs sm:text-sm">
                      {msg.statuses.map((status, idx) => (
                        <li key={idx} className={`${idx === msg.statuses!.length - 1 && isLoading ? 'animate-pulse text-green-700 font-medium' : ''}`}>
                          {status}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* 2. KHU VỰC HIỂN THỊ NỘI DUNG TIN NHẮN */}
                {msg.content && (
                  <div className={`relative px-5 py-3.5 leading-relaxed shadow-sm w-fit ${msg.role === 'user'
                    ? 'bg-green-600 text-white rounded-2xl rounded-tr-sm ml-auto'
                    : 'bg-white text-gray-800 rounded-2xl rounded-tl-sm border border-gray-100'
                    }`}>
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  </div>
                )}

                {/* 3. BONG BÓNG LOADING (Được chuyển vào đúng vị trí ngang hàng Avatar) */}
                {isLoading && msg.id === messages[messages.length - 1].id && msg.role === 'bot' && (!msg.statuses || msg.statuses.length === 0) && !msg.content && (
                  <div className="bg-white border border-gray-100 px-5 py-4 rounded-2xl rounded-tl-sm shadow-sm flex items-center gap-1.5 w-fit">
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-bounce"></div>
                  </div>
                )}

              </div>
            </div>
          ))}

          {/* LƯU Ý: Ở ĐÂY ĐÃ XÓA KHỐI CODE BONG BÓNG CŨ CỦA BẠN RỒI NHÉ */}

          {/* Thẻ div ẩn dùng để scroll */}
          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* INPUT AREA */}
      <footer className="bg-white p-4 shadow-[0_-10px_20px_-10px_rgba(0,0,0,0.05)] border-t border-gray-100">
        <div className="mx-auto max-w-4xl">
          <form onSubmit={handleSend} className="relative flex items-center">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isLoading}
              className="w-full pl-5 pr-14 py-3.5 bg-gray-50 border border-gray-200 rounded-full focus:outline-none focus:border-green-500 focus:ring-2 focus:ring-green-500/20 transition-all disabled:opacity-60"
              placeholder="Nhập câu hỏi của bạn..."
              autoComplete="off"
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="absolute right-2 p-2 bg-green-600 text-white rounded-full hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              <svg className="w-5 h-5 translate-x-[-1px] translate-y-[1px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path>
              </svg>
            </button>
          </form>
          <div className="text-center mt-2 text-xs text-gray-400">
            AI có thể đưa ra thông tin không chính xác. Hãy kiểm tra lại các thông tin quan trọng.
          </div>
        </div>
      </footer>
    </div>
  );
};