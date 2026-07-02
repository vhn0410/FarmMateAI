import { create } from 'zustand';
import { type UserProfile } from '../models/Auth';
interface AuthState {
    user: UserProfile | null;
    isAuthenticated: boolean;
    setAuth: (token: string, user: UserProfile) => void;
    setUser: (user: UserProfile) => void;
    logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
    user: null,
    isAuthenticated: !!localStorage.getItem('access_token'),

    setAuth: (token, user) => {
        localStorage.setItem('access_token', token);
        set({ user, isAuthenticated: true });
    },

    setUser: (user) => {
        set({ user });
    },

    logout: () => {
        localStorage.removeItem('access_token');
        set({ user: null, isAuthenticated: false });
    },
}));