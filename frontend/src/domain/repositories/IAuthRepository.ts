// src/domain/repositories/IAuthRepository.ts
import type { LoginRequest, UserProfile } from '../../models/Auth';

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface IAuthRepository {
  login(credentials: LoginRequest): Promise<TokenResponse>;
  getCurrentUser(): Promise<UserProfile>;
}