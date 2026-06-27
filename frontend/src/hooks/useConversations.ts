// src/application/hooks/useConversations.ts
import { useState, useEffect, useCallback } from 'react';
import { ConversationService } from '../api/conversationService';
import {type Conversation } from '../models/Conversation';

const conversationService = new ConversationService();

export const useConversations = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchConversations = useCallback(async () => {
    setIsLoading(true);
    try {
      // Gọi service, chắc chắn 100% nhận về mảng Conversation[]
      const data = await conversationService.getConversations();
      setConversations(data);
    } catch (error) {
      console.error('Error loading conversation list:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Tự động tải danh sách khi mở trang
  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  return { conversations, isLoading, fetchConversations };
};