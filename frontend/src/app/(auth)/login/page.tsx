"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Eye, EyeOff, Sparkles } from "lucide-react";
import { authService } from "@/services/auth.service";
import { useAuthStore } from "@/store/auth";
import { cn } from "@/lib/utils";
import toast from "react-hot-toast";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextUrl = searchParams.get("next") || "/";
  const { setUser, setTokens } = useAuthStore();
  const [form, setForm] = useState({ email: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      const tokens = await authService.login(form.email, form.password);
      setTokens(tokens.access_token, tokens.refresh_token);
      const user = await authService.getMe();
      setUser(user);
      toast.success("Welcome back!");
      router.replace(nextUrl);
    } catch (err: any) {
      const msg = err.response?.data?.message || "Invalid email or password";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-2xl bg-brand-600/20 border border-brand-500/30 flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-6 h-6 text-brand-400" />
          </div>
          <h1 className="text-2xl font-bold text-neutral-100">Sign in to Lumina</h1>
          <p className="text-neutral-500 mt-1 text-sm">Your AI assistant awaits</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-sm text-red-400">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm text-neutral-400 mb-1.5">Email</label>
            <input
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="you@example.com"
              className={cn(
                "w-full px-4 py-2.5 bg-neutral-800 border border-neutral-700",
                "rounded-xl text-sm text-neutral-100 placeholder:text-neutral-600",
                "focus:outline-none focus:border-brand-500/50 transition-colors"
              )}
            />
          </div>

          <div>
            <label className="block text-sm text-neutral-400 mb-1.5">Password</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                required
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder="••••••••"
                className={cn(
                  "w-full px-4 py-2.5 bg-neutral-800 border border-neutral-700",
                  "rounded-xl text-sm text-neutral-100 placeholder:text-neutral-600",
                  "focus:outline-none focus:border-brand-500/50 transition-colors pr-10"
                )}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-500 hover:text-neutral-300"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2.5 bg-brand-600 hover:bg-brand-500 text-white rounded-xl font-medium text-sm transition-colors disabled:opacity-50 mt-2"
          >
            {isLoading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="text-center text-sm text-neutral-500 mt-6">
          Don&apos;t have an account?{" "}
          <Link href="/signup" className="text-brand-400 hover:text-brand-300">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
