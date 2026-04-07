"use client";

/**
 * Client-side providers wrapper.
 *
 * Separated from layout.tsx because layout is a Server Component —
 * providers with useState/context need to be client components.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { Toaster } from "react-hot-toast";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  // Create QueryClient instance inside component to avoid shared state across SSR requests
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 15_000,         // 15s default — adjust per-query as needed
            gcTime: 5 * 60 * 1000,    // 5min cache
            retry: (failureCount, error) => {
              // Don't retry auth errors
              const status = (error as { response?: { status: number } })?.response?.status;
              if (status === 401 || status === 403 || status === 404) return false;
              return failureCount < 2;
            },
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: "#262626",
            color: "#e5e5e5",
            border: "1px solid #404040",
            borderRadius: "12px",
            fontSize: "13px",
          },
          success: { iconTheme: { primary: "#0ea5e9", secondary: "#fff" } },
        }}
      />
      {process.env.NODE_ENV === "development" && (
        <ReactQueryDevtools initialIsOpen={false} />
      )}
    </QueryClientProvider>
  );
}
