// src/application/hooks/useChatbot.ts
import { useState } from 'react';
import { ChatService } from '../api/chatService';
import { ConversationService } from '../api/conversationService'; // Import thêm service
const chatService = new ChatService();
const conversationService = new ConversationService(); // Khởi tạo service
export interface MessageItem {
  id: string;
  role: 'user' | 'bot';
  content: string;
  statuses?: string[];
}

export const useChatbot = () => {
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
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
      console.error('Error during streaming:', error);
      setMessages(prev => prev.map(msg =>
        msg.id === botMsgId
          ? { ...msg, content: msg.content + '\n\n*(Connection error occurred. Please try again!)*' }
          : msg
      ));
    } finally {
      setIsLoading(false);
    }
  };
  // BỔ SUNG 1: Hàm tải lịch sử tin nhắn
  const loadConversation = async (id: string) => {
    setIsHistoryLoading(true);
    try {
      const data = await conversationService.getConversationById(id);

      // Map dữ liệu từ Backend sang chuẩn của UI
      if (data && data.messages) {
        const historyMessages: MessageItem[] = data.messages.map(msg => ({
          id: msg.id,
          // Kiểm tra sender_type: nếu chứa chữ 'user' thì là user, ngược lại là bot
          role: msg.sender_type.toLowerCase().includes('user') ? 'user' : 'bot',
          content: msg.content,
          statuses: [] // Tin nhắn cũ thường không cần hiển thị lại trạng thái suy nghĩ
        }));

        setMessages(historyMessages);
        setSessionId(data.conversation_id || id);
      }
    } catch (error) {
      console.error('Error loading conversation details:', error);
    } finally {
      setIsHistoryLoading(false);
    }
  };

  // BỔ SUNG 2: Hàm tạo đoạn chat mới
  const startNewChat = () => {
    setMessages([]); // Xóa sạch tin nhắn trên màn hình
    setSessionId(undefined); // Reset lại ID để Backend tạo session mới
  };
  return { messages, isLoading, isHistoryLoading, sendMessage, sessionId, loadConversation, startNewChat };
};