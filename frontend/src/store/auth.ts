/**
 * Auth store — holds the authenticated user and token state.
 *
 * Why Zustand over Context:
 * - No re-render on unrelated state changes
 * - Accessible outside of React components (API interceptors, etc.)
 * - Persist middleware for session restore
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types/api";
import { clearStoredTokens, storeTokens } from "@/lib/api";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setUser: (user: User) => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
  logout: () => void;
  setLoading: (loading: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      isLoading: true,

      setUser: (user) => set({ user, isAuthenticated: true, isLoading: false }),

      setTokens: (accessToken, refreshToken) => {
        storeTokens(accessToken, refreshToken);
      },

      logout: () => {
        clearStoredTokens();
        set({ user: null, isAuthenticated: false, isLoading: false });
      },

      setLoading: (loading) => set({ isLoading: loading }),
    }),
    {
      name: "lumina-auth",
      // Only persist user info, not sensitive tokens
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
);
