export interface ChatRequest {
  query: string;
  session_id?: string;
}

export interface SourceDocument {
  file_name: string;
  hierarchy: string;
  content_snippet: string;
}

export interface ChatData {
  session_id: string;
  answer: string;
  sources: SourceDocument[];
  suggested_questions?: string[];
}

export interface ChatResponse {
  status: string;
  data: ChatData;
  metadata?: any;
}