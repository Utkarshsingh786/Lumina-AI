/**
 * Axios API client with auth interceptors.
 *
 * Design:
 * - Single axios instance — one place for base URL, timeout, headers
 * - Request interceptor: attach Bearer token from storage
 * - Response interceptor: handle 401 → refresh token flow
 * - Errors normalized to APIError shape for consistent handling
 */

import axios, { AxiosError, type AxiosInstance } from "axios";
import type { APIError } from "@/types/api";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api/v1`
  : "/api/v1";  // uses Next.js rewrite in development

export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: {
    "Content-Type": "application/json",
  },
});

// ── Request Interceptor ───────────────────────────────
apiClient.interceptors.request.use((config) => {
  // Read token from memory (not localStorage for security)
  // Tokens are stored in the auth Zustand store
  const token = getStoredAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Response Interceptor ──────────────────────────────
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) prom.reject(error);
    else prom.resolve(token!);
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<APIError>) => {
    const originalRequest = error.config as typeof error.config & {
      _retry?: boolean;
    };

    // ── 429 Rate Limited ───────────────────────────────
    if (error.response?.status === 429) {
      const details = error.response.data?.details as Record<string, unknown> | undefined;
      const retryAfter = typeof details?.retry_after === "number" ? details.retry_after : null;
      const message = retryAfter
        ? `Too many requests — try again in ${retryAfter}s`
        : (error.response.data?.message ?? "Too many requests. Please slow down.");

      // Attach friendly message so callers can display it without re-parsing
      const enriched = new Error(message) as Error & { isRateLimited: true; retryAfter: number | null };
      enriched.isRateLimited = true;
      enriched.retryAfter = retryAfter;
      return Promise.reject(enriched);
    }

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Queue this request until refresh completes
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers!.Authorization = `Bearer ${token}`;
          return apiClient(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = getStoredRefreshToken();
      if (!refreshToken) {
        isRefreshing = false;
        // Force logout
        clearStoredTokens();
        window.location.href = "/login";
        return Promise.reject(error);
      }

      try {
        const { data } = await axios.post(`${BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });
        storeTokens(data.access_token, data.refresh_token);
        processQueue(null, data.access_token);
        originalRequest.headers!.Authorization = `Bearer ${data.access_token}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        clearStoredTokens();
        window.location.href = "/login";
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

// ── Token Storage (in-memory + sessionStorage) ────────
// We use sessionStorage (not localStorage) for the access token —
// cleared on tab close, not accessible to other tabs.
// Refresh token goes in httpOnly cookie in production.

let _accessToken: string | null = null;

export function storeTokens(accessToken: string, refreshToken: string): void {
  _accessToken = accessToken;
  sessionStorage.setItem("lumina_access_token", accessToken);
  // In production: refresh token should be httpOnly cookie set by backend
  sessionStorage.setItem("lumina_refresh_token", refreshToken);
}

export function getStoredAccessToken(): string | null {
  return _accessToken || sessionStorage.getItem("lumina_access_token");
}

export function getStoredRefreshToken(): string | null {
  return sessionStorage.getItem("lumina_refresh_token");
}

export function clearStoredTokens(): void {
  _accessToken = null;
  sessionStorage.removeItem("lumina_access_token");
  sessionStorage.removeItem("lumina_refresh_token");
}
