// src/infrastructure/services/ConversationService.ts
import { axiosClient } from './axiosClient';
import { type Conversation } from '../models/Conversation';

interface ConversationApiResponse {
  status: string;
  data: Conversation[];
}

// BỔ SUNG: Interface cho API chi tiết hội thoại
export interface ConversationDetailResponse {
  status: string;
  conversation_id: string;
  messages: {
    id: string;
    sender_type: string; // Backend trả về sender_type
    content: string;
    created_at: string;
  }[];
}

export class ConversationService {
  async getConversations(): Promise<Conversation[]> {
    const response = await axiosClient.get<ConversationApiResponse>('/api/v1/conversations/');
    return response.data.data; 
  }

  // BỔ SUNG: Hàm lấy tin nhắn của 1 hội thoại cụ thể
  async getConversationById(id: string): Promise<ConversationDetailResponse> {
    const response = await axiosClient.get<ConversationDetailResponse>(`/api/v1/conversations/${id}/messages`);
    return response.data;
  }
}