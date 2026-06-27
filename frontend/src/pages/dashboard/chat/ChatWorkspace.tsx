import React, { useState, useRef, useEffect } from 'react';
import { useChatbot } from '../../../hooks/useChatbot';
import { useConversations } from '../../../hooks/useConversations';
import { BarChart, PieChart } from 'reaviz';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const MessageContent: React.FC<{ content: string; onAction: (query: string) => void }> = ({ content, onAction }) => {
  return (
    <div className="w-full prose prose-sm max-w-none prose-blue">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        urlTransform={(value: string) => value}
        components={{
          a(props) {
            const { href, children, ...rest } = props;
            if (href && href.startsWith('#action:')) {
              // The AI is instructed to use underscores instead of spaces to avoid breaking markdown parsers
              const query = decodeURIComponent(href.replace('#action:', '')).replace(/_/g, ' ');
              return (
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    onAction(query);
                  }}
                  className="inline-block mt-1 mb-1 px-3 py-1.5 bg-blue-50 text-blue-600 font-medium text-sm rounded-lg border border-blue-200 hover:bg-blue-100 transition-colors shadow-sm cursor-pointer no-underline"
                >
                  {children}
                </button>
              );
            }
            return <a href={href} {...rest}>{children}</a>;
          },
          code(props) {
            const {children, className, node, ...rest} = props;
            const match = /language-(\w+)/.exec(className || '');
            
            if (match && match[1] === 'chart') {
              try {
                const jsonStr = String(children).replace(/\n$/, '');
                const chartConfig = JSON.parse(jsonStr);
                return (
                  <div className="my-5 w-full bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg overflow-hidden flex flex-col items-center">
                     <div className="h-64 w-full flex justify-center items-center">
                       {chartConfig.type === 'bar' && <BarChart data={chartConfig.data} />}
                       {chartConfig.type === 'pie' && <PieChart data={chartConfig.data} />}
                     </div>
                     
                     {/* Custom Legend */}
                     <div className="mt-4 flex flex-wrap justify-center gap-x-6 gap-y-2 border-t border-slate-700 w-full pt-4">
                       {chartConfig.data.map((item: any, idx: number) => (
                         <div key={idx} className="flex items-center gap-2 text-sm font-medium text-slate-300">
                           <span className="text-slate-400 font-normal">{item.key}:</span>
                           <span className="text-white text-base">{item.data}</span>
                         </div>
                       ))}
                     </div>
                  </div>
                );
              } catch (e) {
                console.error('Failed to parse chart JSON', e);
                return <code {...rest} className={className}>{children}</code>;
              }
            }
            return <code {...rest} className={className}>{children}</code>;
          }
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export const ChatWorkspace: React.FC = () => {
  const { messages, isLoading: isChatLoading, sendMessage, sessionId, loadConversation, startNewChat } = useChatbot();
  const { conversations, isLoading: isNavLoading } = useConversations();
  const [input, setInput] = useState('');
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isChatLoading) return;
    sendMessage(input);
    setInput('');
  };

  // Group conversations by a generic "Recent" or by date if needed. 
  // For simplicity, we just list them.

  return (
    <div className="flex-1 flex bg-[#E8F1FF] font-sans">
      
      {/* ---------------- MIDDLE SIDEBAR: CHATS LIST ---------------- */}
      <aside className="w-[320px] bg-white flex flex-col shrink-0 border-r border-gray-100 shadow-sm z-10 m-2 rounded-2xl overflow-hidden">
        
        <div className="p-5 flex items-center justify-between border-b border-gray-100">
          <h2 className="text-xl font-bold text-blue-600">Chats</h2>
          <button 
            onClick={startNewChat}
            className="p-1.5 text-gray-500 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4"></path></svg>
          </button>
        </div>

        <div className="p-4 border-b border-gray-100">
          <div className="relative">
            <svg className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
            <input 
              type="text" 
              placeholder="Search.." 
              className="w-full bg-gray-50 pl-10 pr-4 py-2 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-100 transition-shadow"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1 custom-scrollbar">
          {isNavLoading ? (
            <div className="p-4 text-center text-sm text-gray-500">Loading chats...</div>
          ) : conversations.length === 0 ? (
            <div className="p-4 text-center text-sm text-gray-500">No conversations yet.</div>
          ) : (
            conversations.map((conv) => {
              const isActive = sessionId === conv.id;
              return (
                <button 
                  key={conv.id}
                  onClick={() => loadConversation(conv.id)}
                  className={`w-full text-left p-3 rounded-xl transition-all ${
                    isActive 
                      ? 'bg-blue-50 border border-blue-100 shadow-sm' 
                      : 'hover:bg-gray-50 border border-transparent'
                  }`}
                >
                  <div className="flex justify-between items-start mb-1">
                    <h4 className={`font-semibold text-sm truncate pr-2 ${isActive ? 'text-gray-900' : 'text-gray-800'}`}>
                      {conv.title}
                    </h4>
                  </div>
                  <p className="text-xs text-gray-500 line-clamp-2 leading-relaxed">
                    {/* Placeholder snippet since backend might not return last message */}
                    Click to view the conversation details and continue chatting.
                  </p>
                </button>
              );
            })
          )}
        </div>
      </aside>

      {/* ---------------- MAIN CHAT AREA ---------------- */}
      <section className="flex-1 flex flex-col min-w-0 relative my-2 mr-2 bg-transparent">
        
        {/* HEADER */}
        <header className="flex h-16 shrink-0 items-center justify-between px-6 z-10">
          <h2 className="text-xl font-bold text-gray-800">
            {sessionId ? conversations.find(c => c.id === sessionId)?.title || 'Current Chat' : 'New Chat'}
          </h2>
          <div className="flex items-center gap-3">
            <button className="p-2 text-gray-500 hover:bg-white rounded-full transition-colors"><svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg></button>
            <button className="p-2 text-gray-500 hover:bg-white rounded-full transition-colors"><svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 12h.01M12 12h.01M19 12h.01M6 12a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0z"></path></svg></button>
          </div>
        </header>

        {/* MESSAGES LIST */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 scroll-smooth">
          <div className="mx-auto max-w-3xl space-y-6">
            
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center text-center mt-20 text-gray-500 space-y-4">
                <div className="h-16 w-16 bg-blue-100 rounded-full flex items-center justify-center mb-2">
                  <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path></svg>
                </div>
                <h3 className="text-2xl font-semibold text-gray-700">How can I help you today?</h3>
                <p>Send a message to start chatting with FarmMate AI.</p>
              </div>
            )}

            {messages.map((msg) => (
              <div key={msg.id} className={`flex items-start ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                
                <div className={`flex flex-col gap-1 max-w-[85%] sm:max-w-[75%]`}>
                  
                  {/* AI STYLED MESSAGE */}
                  {msg.role === 'bot' && (
                    <div className="flex items-start gap-3 w-full">
                      <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white shadow-sm border border-gray-100 text-blue-600">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h2v2H9V9zm4 0h2v2h-2V9z"></path></svg>
                      </div>
                      
                      <div className="flex flex-col gap-2 w-full">
                        {/* Statuses (Thinking) */}
                        {msg.statuses && msg.statuses.length > 0 && (
                          <div className="bg-white/60 backdrop-blur-sm border border-white/40 rounded-xl p-3 text-sm shadow-sm">
                            <div className="flex items-center gap-2 mb-1.5 font-semibold text-gray-600">
                              {isChatLoading && messages[messages.length - 1].id === msg.id ? (
                                <svg className="w-4 h-4 animate-spin text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                              ) : (
                                <svg className="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                              )}
                              Processing...
                            </div>
                            <ul className="space-y-0.5 ml-6 list-disc text-gray-500 font-mono text-xs">
                              {msg.statuses.map((status, idx) => (
                                <li key={idx} className={`${idx === msg.statuses!.length - 1 && isChatLoading ? 'animate-pulse text-blue-600 font-medium' : ''}`}>
                                  {status}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Content */}
                        {msg.content && (
                          <div className="bg-white px-5 py-4 rounded-2xl shadow-sm border border-gray-50 text-gray-700 leading-relaxed overflow-hidden">
                            <MessageContent content={msg.content} onAction={(query) => sendMessage(query)} />
                          </div>
                        )}
                        
                        {/* Loading dots */}
                        {isChatLoading && msg.id === messages[messages.length - 1].id && (!msg.statuses || msg.statuses.length === 0) && !msg.content && (
                          <div className="bg-white px-5 py-4 rounded-2xl shadow-sm border border-gray-50 w-fit flex items-center gap-1.5">
                            <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                            <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                            <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"></div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* USER STYLED MESSAGE */}
                  {msg.role === 'user' && (
                    <div className="bg-white px-5 py-4 rounded-2xl shadow-sm border border-gray-50 text-gray-800 leading-relaxed ml-auto">
                      <div className="whitespace-pre-wrap">{msg.content}</div>
                    </div>
                  )}
                  
                </div>
              </div>
            ))}

            <div ref={messagesEndRef} />
          </div>
        </main>

        {/* INPUT AREA */}
        <footer className="px-6 pb-6 pt-2">
          <div className="mx-auto max-w-3xl">
            <form onSubmit={handleSend} className="relative flex items-center bg-white rounded-xl shadow-sm border border-gray-100 p-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={isChatLoading}
                className="flex-1 bg-transparent pl-4 py-2 focus:outline-none text-gray-700 disabled:opacity-60 placeholder-gray-400"
                placeholder="Ask me anything..."
                autoComplete="off"
              />
              <div className="flex items-center gap-1 pr-2">
                <button type="button" className="p-2 text-gray-400 hover:text-gray-600 transition-colors">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                </button>
                <button type="button" className="p-2 text-gray-400 hover:text-gray-600 transition-colors">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"></path></svg>
                </button>
                <button
                  type="submit"
                  disabled={isChatLoading || !input.trim()}
                  className="p-2 ml-1 text-blue-600 hover:bg-blue-50 rounded-lg disabled:text-gray-300 disabled:bg-transparent disabled:cursor-not-allowed transition-colors"
                >
                  <svg className="w-5 h-5 translate-x-[1px]" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path>
                  </svg>
                </button>
              </div>
            </form>
          </div>
        </footer>
      </section>

    </div>
  );
};