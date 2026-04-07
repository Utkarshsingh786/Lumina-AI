"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { Sidebar } from "@/components/sidebar/Sidebar";
import { useAuthStore } from "@/store/auth";
import { useChatStore } from "@/store/chat";
import { authService } from "@/services/auth.service";

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  const { setUser, logout } = useAuthStore();
  const { sidebarOpen, setSidebarOpen } = useChatStore();
  const router = useRouter();
  // sessionChecked tracks whether we've validated the token with the server.
  // We always validate on mount — Zustand-persisted isAuthenticated may be stale
  // (e.g. tokens cleared after browser restart / sessionStorage lost on tab close).
  const [sessionChecked, setSessionChecked] = useState(false);

  useEffect(() => {
    const restoreSession = async () => {
      try {
        // Always call /auth/me — the 401 interceptor handles token refresh
        const user = await authService.getMe();
        setUser(user);
        setSessionChecked(true);
      } catch {
        // Either tokens are gone or refresh also failed (interceptor already redirected)
        logout();
        router.replace("/login");
        // Don't set sessionChecked — navigation is in progress
      }
    };
    restoreSession();
  }, []);

  if (!sessionChecked) {
    return (
      <div className="flex h-screen items-center justify-center bg-neutral-950">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-neutral-950">
      {/* ── Desktop sidebar: always visible as flex item ── */}
      <div className="hidden md:flex md:flex-shrink-0">
        <Sidebar />
      </div>

      {/* ── Mobile sidebar: fixed overlay, slides in from left ── */}
      <AnimatePresence>
        {sidebarOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              key="sidebar-backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-40 bg-black/60 md:hidden"
              onClick={() => setSidebarOpen(false)}
            />
            {/* Sidebar panel */}
            <motion.div
              key="sidebar-panel"
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", stiffness: 350, damping: 35 }}
              className="fixed inset-y-0 left-0 z-50 md:hidden"
            >
              <Sidebar onClose={() => setSidebarOpen(false)} />
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* ── Main content ── */}
      <main className="flex-1 overflow-hidden min-w-0">{children}</main>
    </div>
  );
}
