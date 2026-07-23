// src/infrastructure/services/ConversationService.ts
import { axiosClient } from './axiosClient';
import { type Conversation } from '../models/Conversation';

interface ConversationApiResponse {
  status: string;
  data: Conversation[];
}

// Additional interface for detailed conversation API responses
export interface ConversationDetailResponse {
  status: string;
  conversation_id: string;
  messages: {
    id: string;
    sender_type: string; // Backend returns sender_type
    content: string;
    created_at: string;
  }[];
}

export class ConversationService {
  async getConversations(): Promise<Conversation[]> {
    const response = await axiosClient.get<ConversationApiResponse>('/api/v1/conversations/');
    return response.data.data; 
  }

  // Additional helper to fetch messages for a specific conversation
  async getConversationById(id: string): Promise<ConversationDetailResponse> {
    const response = await axiosClient.get<ConversationDetailResponse>(`/api/v1/conversations/${id}/messages`);
    return response.data;
  }

  async deleteConversation(id: string): Promise<void> {
    await axiosClient.delete(`/api/v1/conversations/${id}`);
  }
}