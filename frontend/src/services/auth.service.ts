import { apiClient } from "@/lib/api";
import type { TokenResponse, User } from "@/types/api";

export const authService = {
  async register(data: {
    email: string;
    username: string;
    password: string;
    full_name?: string;
  }): Promise<TokenResponse> {
    const res = await apiClient.post<TokenResponse>("/auth/register", data);
    return res.data;
  },

  async login(email: string, password: string): Promise<TokenResponse> {
    const res = await apiClient.post<TokenResponse>("/auth/login", { email, password });
    return res.data;
  },

  async getMe(): Promise<User> {
    const res = await apiClient.get<User>("/auth/me");
    return res.data;
  },

  async updateMe(data: Partial<User>): Promise<User> {
    const res = await apiClient.patch<User>("/auth/me", data);
    return res.data;
  },
};
