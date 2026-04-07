/**
 * Axios API client with auth interceptors and global error handling.
 *
 * Design:
 * - Single axios instance — one place for base URL, timeout, headers
 * - Request interceptor: attach Bearer token from storage
 * - Response interceptor: 401 → refresh token flow (skipped for auth endpoints)
 * - Global toasts for network failures, server errors, and permission errors
 * - Auth endpoint 401s (wrong credentials) bubble up to forms for inline display
 */

import axios, { AxiosError, type AxiosInstance } from "axios";
import toast from "react-hot-toast";
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

// ── Auth endpoint detection ───────────────────────────
// 401s on these paths mean "bad credentials", not "expired session".
// They must NOT trigger the refresh/redirect interceptor — let them
// reach the form's catch block for inline error display.
const AUTH_ENDPOINTS = ["/auth/login", "/auth/register", "/auth/refresh", "/auth/logout"];

function isAuthEndpoint(url: string | undefined): boolean {
  return AUTH_ENDPOINTS.some((p) => url?.includes(p));
}

// ── Request Interceptor ───────────────────────────────
apiClient.interceptors.request.use((config) => {
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

    // ── Network / timeout errors (no response from server) ──
    if (!error.response) {
      const isTimeout = error.code === "ECONNABORTED" || error.message?.includes("timeout");
      if (isTimeout) {
        toast.error("Request timed out. Please try again.", { id: "timeout-error" });
      } else {
        toast.error("Connection failed. Check your internet connection.", {
          id: "network-error",
        });
      }
      return Promise.reject(error);
    }

    const status = error.response.status;
    const data = error.response.data;
    const url = originalRequest?.url;

    // ── 429 Rate Limited ──────────────────────────────────
    if (status === 429) {
      const details = data?.details as Record<string, unknown> | undefined;
      const retryAfter = typeof details?.retry_after === "number" ? details.retry_after : null;
      const message = retryAfter
        ? `Too many requests — try again in ${retryAfter}s`
        : (data?.message ?? "Too many requests. Please slow down.");

      toast.error(message, { id: "rate-limit" });

      const enriched = new Error(message) as Error & {
        isRateLimited: true;
        retryAfter: number | null;
      };
      enriched.isRateLimited = true;
      enriched.retryAfter = retryAfter;
      return Promise.reject(enriched);
    }

    // ── 401 Unauthorized ──────────────────────────────────
    // Auth endpoints: let the error bubble up to the form (wrong credentials).
    // Other endpoints: try token refresh, then redirect to login.
    if (status === 401) {
      if (isAuthEndpoint(url)) {
        // Bad credentials — caller's catch block will show the error inline
        return Promise.reject(error);
      }

      if (!originalRequest._retry) {
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
          clearStoredTokens();
          window.location.href = "/login";
          return Promise.reject(error);
        }

        try {
          const { data: tokenData } = await axios.post(`${BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          });
          storeTokens(tokenData.access_token, tokenData.refresh_token);
          processQueue(null, tokenData.access_token);
          originalRequest.headers!.Authorization = `Bearer ${tokenData.access_token}`;
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
    }

    // ── 403 Forbidden ──────────────────────────────────────
    if (status === 403) {
      toast.error(data?.message || "You don't have permission to do this.", {
        id: "forbidden",
      });
    }

    // ── 5xx Server Errors ──────────────────────────────────
    if (status >= 500) {
      const serverMessage =
        status === 503
          ? "Service temporarily unavailable. Try again shortly."
          : status === 504
          ? "The server took too long to respond. Try again."
          : data?.message || "Something went wrong on our end. Please try again.";

      toast.error(serverMessage, { id: `server-${status}` });
    }

    return Promise.reject(error);
  }
);

// ── Token Storage ─────────────────────────────────────
// sessionStorage: cleared on tab close, not accessible cross-tab.
// In production, refresh token should move to an httpOnly cookie.

let _accessToken: string | null = null;

export function storeTokens(accessToken: string, refreshToken: string): void {
  _accessToken = accessToken;
  sessionStorage.setItem("lumina_access_token", accessToken);
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
