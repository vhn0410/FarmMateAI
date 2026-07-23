import { axiosClient } from './axiosClient';
import type { ChatRequest, ChatResponse } from '../models/Chat';

// Define the standard response shape expected from the backend
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

  // Generator that yields objects instead of raw strings
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
    let buffer = ''; // Buffer to hold JSON fragments that may be split across chunks

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Split JSON objects (handles cases where the backend emits adjacent }{ fragments)
      buffer = buffer.replace(/}{/g, '}\n{');
      const lines = buffer.split('\n');

      // Keep the last fragment in the buffer because it may be an incomplete JSON payload
      buffer = lines.pop() || '';

      for (const line of lines) {
        let cleanLine = line.trim();
        if (!cleanLine) continue;

        // Remove the "data: " prefix if the backend includes it (standard SSE)
        if (cleanLine.startsWith('data: ')) {
          cleanLine = cleanLine.substring(6).trim();
        }

        if (cleanLine === '[DONE]') continue;

        try {
          // Parse into an object and yield it
          const data = JSON.parse(cleanLine) as StreamEvent;
          yield data;
        } catch (e) {
          console.warn('Skipping invalid non-JSON chunk:', cleanLine);
        }
      }
    }

    // Parse the final remaining buffer if anything is left
    if (buffer.trim()) {
      let cleanLine = buffer.replace(/^data:\s*/, '').trim();
      if (cleanLine && cleanLine !== '[DONE]') {
        try { yield JSON.parse(cleanLine); } catch (e) {}
      }
    }
  }

  // Stream dedicated to document chat
  async *sendDocumentStreamMessage(request: ChatRequest, fileIds: string[]): AsyncGenerator<StreamEvent, void, unknown> {
    const token = localStorage.getItem('access_token');
    const baseUrl = import.meta.env.VITE_API_BASE_URL !== undefined ? import.meta.env.VITE_API_BASE_URL : 'http://127.0.0.1:8000';
    
    // Attach file_ids to the request payload
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