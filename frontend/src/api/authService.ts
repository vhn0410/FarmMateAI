// src/infrastructure/services/AuthService.ts
import type { IAuthRepository, TokenResponse } from '../domain/repositories/IAuthRepository';
import type { LoginRequest, UserProfile } from '../models/Auth';
import { axiosClient } from './axiosClient';

export class AuthService implements IAuthRepository {
  async login(credentials: LoginRequest): Promise<TokenResponse> {
    // Ép kiểu dữ liệu về dạng x-www-form-urlencoded theo đúng OpenAPI Schema
    const params = new URLSearchParams();
    params.append('username', credentials.username);
    params.append('password', credentials.password);

    const response = await axiosClient.post<TokenResponse>('/api/v1/auth/login', params, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    return response.data;
  }

  async getCurrentUser(): Promise<UserProfile> {
    const response = await axiosClient.get<UserProfile>('/api/v1/users/me');
    return response.data;
  }
}