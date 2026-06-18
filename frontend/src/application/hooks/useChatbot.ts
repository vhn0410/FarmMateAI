// src/application/hooks/useChatbot.ts
import { useState } from 'react';
import { ChatService } from '../../infrastructure/services/ChatService';

const chatService = new ChatService();

export interface MessageItem {
  id: string;
  role: 'user' | 'bot';
  content: string;
  statuses?: string[]; 
}

export const useChatbot = () => {
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);

  const sendMessage = async (text: string) => {
    if (!text.trim()) return;

    const userMsgId = Date.now().toString();
    const botMsgId = (Date.now() + 1).toString();

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', content: text },
      { id: botMsgId, role: 'bot', content: '', statuses: [] } 
    ]);
    setIsLoading(true);

    try {
      const stream = chatService.sendStreamMessage({ query: text, session_id: sessionId });

      for await (const data of stream) {
        if (data.event === 'status' && data.message) {
          
          setMessages(prev => prev.map(msg => {
            if (msg.id === botMsgId) {
              const currentStatuses = msg.statuses || [];
              if (currentStatuses[currentStatuses.length - 1] !== data.message) {
                // FIX LỖI Ở ĐÂY: Thêm "as string" để báo cho TypeScript biết chắc chắn nó là string
                return { ...msg, statuses: [...currentStatuses, data.message as string] };
              }
            }
            return msg;
          }));
          
        } else if (data.event === 'token' && data.text) {
          setMessages(prev => prev.map(msg => 
            msg.id === botMsgId ? { ...msg, content: msg.content + data.text } : msg
          ));
          
        } else if (data.event === 'done') {
          if (data.session_id) setSessionId(data.session_id);
        }
      }
    } catch (error) {
      console.error('Lỗi khi stream:', error);
      setMessages(prev => prev.map(msg => 
        msg.id === botMsgId 
          ? { ...msg, content: msg.content + '\n\n*(Đã xảy ra lỗi kết nối. Vui lòng thử lại!)*' }
          : msg
      ));
    } finally {
      setIsLoading(false);
    }
  };

  return { messages, isLoading, sendMessage, sessionId };
};