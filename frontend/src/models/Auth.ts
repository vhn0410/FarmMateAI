export interface LoginRequest {
  username: string;
  password: string;
}

export interface UserProfile {
  // Assumed fields based on the /api/v1/users/me API
  id: string;
  username: string;
  full_name: string;
  email?: string;
  role?: string;
  roles?: string[];
}