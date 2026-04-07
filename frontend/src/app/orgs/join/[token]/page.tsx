"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Building2, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { apiClient, getStoredAccessToken } from "@/lib/api";

export default function JoinOrgPage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const [status, setStatus] = useState<"idle" | "joining" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const isAuthenticated = !!getStoredAccessToken();

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace(`/login?next=/orgs/join/${token}`);
    }
  }, [isAuthenticated, token, router]);

  const handleJoin = async () => {
    setStatus("joining");
    try {
      const res = await apiClient.post(`/orgs/join/${token}`);
      setMessage(res.data?.message ?? "Successfully joined!");
      setStatus("success");
      setTimeout(() => router.replace("/organization"), 2000);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { message?: string } } };
      setMessage(err?.response?.data?.message ?? "Invalid or expired invite token.");
      setStatus("error");
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-950">
        <Loader2 className="w-6 h-6 text-brand-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-950 px-4">
      <div className="w-full max-w-sm rounded-2xl border border-neutral-800 bg-neutral-900 p-8 text-center">
        {status === "success" ? (
          <>
            <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto mb-4" />
            <h1 className="text-lg font-semibold text-neutral-100 mb-1">Joined!</h1>
            <p className="text-sm text-neutral-400">{message}</p>
            <p className="text-xs text-neutral-600 mt-2">Redirecting…</p>
          </>
        ) : status === "error" ? (
          <>
            <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
            <h1 className="text-lg font-semibold text-neutral-100 mb-1">Invite error</h1>
            <p className="text-sm text-neutral-400">{message}</p>
            <button
              onClick={() => router.replace("/organization")}
              className="mt-4 text-sm text-brand-400 hover:text-brand-300 transition-colors"
            >
              Go to Organizations
            </button>
          </>
        ) : (
          <>
            <Building2 className="w-12 h-12 text-brand-400 mx-auto mb-4" />
            <h1 className="text-lg font-semibold text-neutral-100 mb-1">Organisation invite</h1>
            <p className="text-sm text-neutral-400 mb-6">
              You've been invited to join an organisation on Lumina.
            </p>
            <button
              onClick={handleJoin}
              disabled={status === "joining"}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium transition-colors disabled:opacity-50"
            >
              {status === "joining" ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                "Accept invite"
              )}
            </button>
            <button
              onClick={() => router.replace("/organization")}
              className="mt-3 w-full text-sm text-neutral-500 hover:text-neutral-300 transition-colors"
            >
              Cancel
            </button>
          </>
        )}
      </div>
    </div>
  );
}
