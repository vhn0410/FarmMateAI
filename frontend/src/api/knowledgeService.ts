import { axiosClient } from './axiosClient';

export interface KnowledgeFile {
  id: string;
  name: string;
  webViewLink?: string;
  webContentLink?: string;
}

export const knowledgeService = {
  getFiles: async (): Promise<KnowledgeFile[]> => {
    const response = await axiosClient.get('/api/v1/documents/knowledge-base/files');
    return response.data.data;
  },
  uploadFile: async (file: File): Promise<KnowledgeFile> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await axiosClient.post('/api/v1/documents/knowledge-base/files/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    return response.data.data;
  }
};
