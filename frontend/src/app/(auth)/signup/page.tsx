"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Sparkles } from "lucide-react";
import { authService } from "@/services/auth.service";
import { useAuthStore } from "@/store/auth";
import { cn } from "@/lib/utils";
import toast from "react-hot-toast";

export default function SignupPage() {
  const router = useRouter();
  const { setUser, setTokens } = useAuthStore();
  const [form, setForm] = useState({
    email: "",
    username: "",
    password: "",
    full_name: "",
  });
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrors({});
    try {
      const tokens = await authService.register(form);
      setTokens(tokens.access_token, tokens.refresh_token);
      const user = await authService.getMe();
      setUser(user);
      toast.success("Account created! Welcome to Lumina.");
      router.replace("/");
    } catch (err: any) {
      const data = err.response?.data;
      if (data?.error_code === "EMAIL_EXISTS") {
        setErrors({ email: "This email is already registered" });
      } else if (data?.error_code === "USERNAME_EXISTS") {
        setErrors({ username: "This username is taken" });
      } else {
        setErrors({ form: data?.message || "Registration failed" });
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-2xl bg-brand-600/20 border border-brand-500/30 flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-6 h-6 text-brand-400" />
          </div>
          <h1 className="text-2xl font-bold text-neutral-100">Create your account</h1>
          <p className="text-neutral-500 mt-1 text-sm">Free to start — no credit card needed</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {errors.form && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-sm text-red-400">
              {errors.form}
            </div>
          )}

          {[
            { key: "full_name", label: "Full name", type: "text", placeholder: "Jane Smith" },
            { key: "username", label: "Username", type: "text", placeholder: "janesmith" },
            { key: "email", label: "Email", type: "email", placeholder: "jane@example.com" },
            { key: "password", label: "Password", type: "password", placeholder: "Min 8 chars, 1 uppercase, 1 number" },
          ].map(({ key, label, type, placeholder }) => (
            <div key={key}>
              <label className="block text-sm text-neutral-400 mb-1.5">{label}</label>
              <input
                type={type}
                required={key !== "full_name"}
                value={(form as any)[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                placeholder={placeholder}
                className={cn(
                  "w-full px-4 py-2.5 bg-neutral-800 border rounded-xl text-sm text-neutral-100",
                  "placeholder:text-neutral-600 focus:outline-none transition-colors",
                  errors[key]
                    ? "border-red-500/50 focus:border-red-500"
                    : "border-neutral-700 focus:border-brand-500/50"
                )}
              />
              {errors[key] && (
                <p className="text-xs text-red-400 mt-1">{errors[key]}</p>
              )}
            </div>
          ))}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2.5 bg-brand-600 hover:bg-brand-500 text-white rounded-xl font-medium text-sm transition-colors disabled:opacity-50 mt-2"
          >
            {isLoading ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="text-center text-sm text-neutral-500 mt-6">
          Already have an account?{" "}
          <Link href="/login" className="text-brand-400 hover:text-brand-300">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
