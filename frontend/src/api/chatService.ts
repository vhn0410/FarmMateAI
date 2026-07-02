import { axiosClient } from './axiosClient';
import type { ChatRequest, ChatResponse } from '../models/Chat';

// Định nghĩa cấu trúc chuẩn theo Backend của bạn
export interface StreamEvent {
  event: 'status' | 'token' | 'done' | 'error';
  message?: string;
  text?: string;
  session_id?: string;
  sources?: any[];
  suggested_questions?: string[];
  metadata?: any;
}

export class ChatService {
  async sendNormalMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await axiosClient.post<ChatResponse>('/api/v1/chat/', request);
    return response.data;
  }

  // Generator trả về Object thay vì string thô
  async *sendStreamMessage(request: ChatRequest): AsyncGenerator<StreamEvent, void, unknown> {
    const token = localStorage.getItem('access_token');
    const baseUrl = import.meta.env.VITE_API_BASE_URL !== undefined ? import.meta.env.VITE_API_BASE_URL : 'http://127.0.0.1:8000';
    const response = await fetch(`${baseUrl}/api/v1/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      body: JSON.stringify(request)
    });

    if (!response.ok) throw new Error(`Streaming failed: ${response.status}`);
    if (!response.body) throw new Error('ReadableStream not supported.');

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = ''; // Dùng buffer để hứng các mảnh JSON bị cắt đứt giữa chừng

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Tách các JSON object (xử lý case backend gửi dính liền }{ )
      buffer = buffer.replace(/}{/g, '}\n{');
      const lines = buffer.split('\n');

      // Giữ lại mảnh cuối cùng trong buffer (vì nó có thể là một JSON chưa hoàn thiện)
      buffer = lines.pop() || '';

      for (const line of lines) {
        let cleanLine = line.trim();
        if (!cleanLine) continue;

        // Xóa tiền tố "data: " nếu backend có thêm vào (Chuẩn SSE)
        if (cleanLine.startsWith('data: ')) {
          cleanLine = cleanLine.substring(6).trim();
        }

        if (cleanLine === '[DONE]') continue;

        try {
          // Ép kiểu thành Object và ném ra ngoài
          const data = JSON.parse(cleanLine) as StreamEvent;
          yield data;
        } catch (e) {
          console.warn('Bỏ qua chunk không phải JSON hợp lệ:', cleanLine);
        }
      }
    }

    // Parse nốt buffer cuối cùng nếu còn sót lại
    if (buffer.trim()) {
      let cleanLine = buffer.replace(/^data:\s*/, '').trim();
      if (cleanLine && cleanLine !== '[DONE]') {
        try { yield JSON.parse(cleanLine); } catch (e) {}
      }
    }
  }

  // Stream dành riêng cho Document Chat
  async *sendDocumentStreamMessage(request: ChatRequest, fileIds: string[]): AsyncGenerator<StreamEvent, void, unknown> {
    const token = localStorage.getItem('access_token');
    const baseUrl = import.meta.env.VITE_API_BASE_URL !== undefined ? import.meta.env.VITE_API_BASE_URL : 'http://127.0.0.1:8000';
    
    // Gắn thêm file_ids vào request
    const payload = {
      ...request,
      file_ids: fileIds
    };

    const response = await fetch(`${baseUrl}/api/v1/chat/document/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) throw new Error(`Streaming failed: ${response.status}`);
    if (!response.body) throw new Error('ReadableStream not supported.');

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      buffer = buffer.replace(/}{/g, '}\n{');
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        let cleanLine = line.trim();
        if (!cleanLine) continue;
        if (cleanLine.startsWith('data: ')) {
          cleanLine = cleanLine.substring(6).trim();
        }
        if (cleanLine === '[DONE]') return;
        try {
          const data = JSON.parse(cleanLine) as StreamEvent;
          yield data;
        } catch (e) {
          console.error('JSON Parse error:', e, cleanLine);
        }
      }
    }
    
    if (buffer.trim()) {
      let cleanLine = buffer.replace(/^data:\s*/, '').trim();
      if (cleanLine && cleanLine !== '[DONE]') {
        try { yield JSON.parse(cleanLine); } catch (e) {}
      }
    }
  }
}