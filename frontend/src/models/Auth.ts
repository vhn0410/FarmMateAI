export interface LoginRequest {
  username: string;
  password: string;
}

export interface UserProfile {
  // Giả định các field dựa trên API /api/v1/users/me
  id: string;
  username: string;
  full_name: string;
  email?: string;
  roles?: string[];
}