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
      // Call the service and expect a Conversation[] array
      const data = await conversationService.getConversations();
      setConversations(data);
    } catch (error) {
      console.error('Error loading conversation list:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Automatically load the list when the page opens
  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  // Delete a conversation
  const deleteConversation = useCallback(async (id: string) => {
    try {
      await conversationService.deleteConversation(id);
      // If deletion succeeds, either refetch or remove it from the list
      setConversations(prev => prev.filter(c => c.id !== id));
      return true;
    } catch (error) {
      console.error('Error deleting conversation:', error);
      return false;
    }
  }, []);

  return { conversations, isLoading, fetchConversations, deleteConversation };
};