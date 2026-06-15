import { create } from 'zustand';
import { type UserProfile } from '../../domain/models/Auth';
interface AuthState {
    user: UserProfile | null;
    isAuthenticated: boolean;
    setAuth: (token: string, user: UserProfile) => void;
    logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
    user: null,
    isAuthenticated: !!localStorage.getItem('access_token'),

    setAuth: (token, user) => {
        localStorage.setItem('access_token', token);
        set({ user, isAuthenticated: true });
    },

    logout: () => {
        localStorage.removeItem('access_token');
        set({ user: null, isAuthenticated: false });
    },
}));