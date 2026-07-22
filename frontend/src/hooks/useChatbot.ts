// src/application/hooks/useChatbot.ts
import { useState } from 'react';
import { ChatService } from '../api/chatService';
import { ConversationService } from '../api/conversationService'; // Add the conversation service
const chatService = new ChatService();
const conversationService = new ConversationService(); // Initialize the service
export interface MessageItem {
  id: string;
  role: 'user' | 'bot';
  content: string;
  statuses?: string[];
  sources?: any[];
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
                // Fix: add "as string" so TypeScript knows it is definitely a string
                return { ...msg, statuses: [...currentStatuses, data.message as string] };
              }
            }
            return msg;
          }));

        } else if (data.event === 'sources' && data.sources) {
          setMessages(prev => prev.map(msg =>
            msg.id === botMsgId ? { ...msg, sources: data.sources } : msg
          ));

        } else if (data.event === 'token' && data.text) {
          setMessages(prev => prev.map(msg =>
            msg.id === botMsgId ? { ...msg, content: msg.content + data.text } : msg
          ));

        } else if (data.event === 'done') {
          if (data.session_id) setSessionId(data.session_id);
        } else if (data.event === 'error') {
          setMessages(prev => prev.map(msg =>
            msg.id === botMsgId ? { ...msg, content: msg.content + '\n\n*(Lỗi: ' + data.message + ')*' } : msg
          ));
        }
      }
    } catch (error) {
      console.error('Error during streaming:', error);
      setMessages(prev => [...prev, { id: Date.now().toString(), role: 'bot', content: 'Có lỗi xảy ra, vui lòng thử lại sau.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  const sendDocumentMessage = async (text: string, fileIds: string[]) => {
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
      const stream = chatService.sendDocumentStreamMessage({ query: text, session_id: sessionId }, fileIds);

      for await (const data of stream) {
        if (data.event === 'status' && data.message) {
          setMessages(prev => prev.map(msg => {
            if (msg.id === botMsgId) {
              const currentStatuses = msg.statuses || [];
              if (currentStatuses[currentStatuses.length - 1] !== data.message) {
                return { ...msg, statuses: [...currentStatuses, data.message as string] };
              }
            }
            return msg;
          }));
        } else if (data.event === 'sources' && data.sources) {
          setMessages(prev => prev.map(msg =>
            msg.id === botMsgId ? { ...msg, sources: data.sources } : msg
          ));
        } else if (data.event === 'token' && data.text) {
          setMessages(prev => prev.map(msg =>
            msg.id === botMsgId ? { ...msg, content: msg.content + data.text } : msg
          ));
        } else if (data.event === 'done') {
          if (data.session_id) setSessionId(data.session_id);
        } else if (data.event === 'error') {
          setMessages(prev => prev.map(msg =>
            msg.id === botMsgId ? { ...msg, content: msg.content + '\n\n*(Lỗi: ' + data.message + ')*' } : msg
          ));
        }
      }
    } catch (error) {
      console.error('Error during streaming:', error);
      setMessages(prev => [...prev, { id: Date.now().toString(), role: 'bot', content: 'Có lỗi xảy ra, vui lòng thử lại sau.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  // Additional helper: load message history
  const loadConversation = async (id: string) => {
    setIsHistoryLoading(true);
    try {
      const data = await conversationService.getConversationById(id);

      // Map the backend payload into the UI-friendly format
      if (data && data.messages) {
        const historyMessages: MessageItem[] = data.messages.map(msg => ({
          id: msg.id,
          // Determine the sender role from sender_type: if it contains 'user' then it is a user, otherwise it is a bot
          role: msg.sender_type.toLowerCase().includes('user') ? 'user' : 'bot',
          content: msg.content,
          statuses: [] // Historical messages usually do not need to show thinking states again
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

  // Additional helper: start a new chat session
  const startNewChat = () => {
    setMessages([]); // Clear the visible messages
    setSessionId(undefined); // Reset the ID so the backend can create a new session
  };
  return { messages, isLoading, isHistoryLoading, sendMessage, sendDocumentMessage, sessionId, loadConversation, startNewChat };
};