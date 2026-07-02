import { axiosClient } from './axiosClient';

export interface KnowledgeFile {
  id: string;
  name: string;
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
  },
  deleteFile: async (fileId: string): Promise<void> => {
    await axiosClient.delete(`/api/v1/documents/knowledge-base/files/${fileId}`);
  },
  getFileMarkdown: async (fileId: string): Promise<string> => {
    const response = await axiosClient.get(`/api/v1/documents/knowledge-base/files/${fileId}/markdown`);
    return response.data.data;
  },
  getFileChunks: async (fileId: string): Promise<any[]> => {
    const response = await axiosClient.get(`/api/v1/documents/knowledge-base/files/${fileId}/chunks`);
    return response.data.data;
  },
  getFileStreamUrl: async (fileId: string): Promise<string> => {
    const response = await axiosClient.get(`/api/v1/documents/knowledge-base/files/${fileId}/stream`, {
      responseType: 'blob'
    });
    return URL.createObjectURL(response.data);
  }
};
