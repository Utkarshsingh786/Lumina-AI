"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Shield,
  Users,
  MessageSquare,
  FileText,
  Activity,
  Search,
  ChevronLeft,
  ChevronRight,
  DollarSign,
  Menu,
  Loader2,
} from "lucide-react";
import toast from "react-hot-toast";
import { apiClient } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { useChatStore } from "@/store/chat";
import { cn } from "@/lib/utils";
import type { AdminStats, User, PaginatedResponse } from "@/types/api";

// ── Data fetchers ──────────────────────────────────────
const fetchStats = async (): Promise<AdminStats> => (await apiClient.get("/admin/stats")).data;
const fetchUsers = async (page: number, search: string): Promise<PaginatedResponse<User>> =>
  (await apiClient.get(`/admin/users?page=${page}&page_size=20${search ? `&search=${encodeURIComponent(search)}` : ""}`)).data;
const fetchUsage = async (): Promise<{ total_tokens: number; total_cost_usd: number; total_requests: number; period_days: number; by_provider: Array<{ provider: string; tokens: number; cost_usd: number; requests: number }> }> =>
  (await apiClient.get("/admin/usage?days=30")).data;

export default function AdminPage() {
  const { user } = useAuthStore();
  const toggleSidebar = useChatStore((s) => s.toggleSidebar);
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");

  // Guard: only admins
  if (user?.role !== "admin") {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-neutral-950 gap-3 text-neutral-500">
        <Shield className="w-10 h-10" />
        <p className="text-sm">Admin access required</p>
      </div>
    );
  }

  const { data: stats } = useQuery({ queryKey: ["admin-stats"], queryFn: fetchStats, staleTime: 30_000 });
  const { data: usersPage, isLoading: usersLoading } = useQuery({
    queryKey: ["admin-users", page, search],
    queryFn: () => fetchUsers(page, search),
    staleTime: 30_000,
  });
  const { data: usageData } = useQuery({ queryKey: ["admin-usage"], queryFn: fetchUsage, staleTime: 60_000 });

  const updateUser = useMutation({
    mutationFn: ({ id, ...body }: { id: string; role?: string; is_active?: boolean }) =>
      apiClient.patch(`/admin/users/${id}`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success("User updated");
    },
    onError: () => toast.error("Update failed"),
  });

  const fmtNum = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(1)}K` : n.toString();

  return (
    <div className="flex flex-col h-full overflow-y-auto bg-neutral-950 scrollbar-thin scrollbar-thumb-neutral-800">
      {/* Mobile header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-neutral-800 md:hidden">
        <button onClick={toggleSidebar} className="p-1.5 rounded-lg text-neutral-500 hover:text-neutral-200 hover:bg-neutral-800 transition-colors">
          <Menu className="w-5 h-5" />
        </button>
        <h1 className="text-sm font-semibold text-neutral-200">Admin</h1>
      </div>

      <div className="max-w-4xl mx-auto w-full px-4 py-8 space-y-6">
        <div>
          <h1 className="text-xl font-semibold text-neutral-100 flex items-center gap-2">
            <Shield className="w-5 h-5 text-amber-400" /> Admin Panel
          </h1>
          <p className="text-sm text-neutral-500 mt-0.5">System overview and user management</p>
        </div>

        {/* Stats cards */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard icon={<Users className="w-4 h-4" />} label="Users" value={fmtNum(stats.users.total)} sub={`+${stats.users.new_24h} today`} />
            <StatCard icon={<MessageSquare className="w-4 h-4" />} label="Conversations" value={fmtNum(stats.conversations.total)} sub={`+${stats.conversations.new_24h} today`} />
            <StatCard icon={<Activity className="w-4 h-4" />} label="Messages" value={fmtNum(stats.messages.total)} />
            <StatCard icon={<FileText className="w-4 h-4" />} label="Documents" value={fmtNum(stats.documents.total)} />
          </div>
        )}

        {/* Usage summary */}
        {usageData && (
          <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-neutral-800">
              <DollarSign className="w-4 h-4 text-neutral-500" />
              <h2 className="text-sm font-medium text-neutral-300">Global usage (last 30 days)</h2>
            </div>
            <div className="p-4 grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-lg font-semibold text-neutral-100">{fmtNum(usageData.total_tokens)}</p>
                <p className="text-xs text-neutral-500">tokens</p>
              </div>
              <div>
                <p className="text-lg font-semibold text-emerald-400">${usageData.total_cost_usd.toFixed(4)}</p>
                <p className="text-xs text-neutral-500">USD cost</p>
              </div>
              <div>
                <p className="text-lg font-semibold text-neutral-100">{fmtNum(usageData.total_requests)}</p>
                <p className="text-xs text-neutral-500">requests</p>
              </div>
            </div>
            {usageData.by_provider.length > 0 && (
              <div className="border-t border-neutral-800 divide-y divide-neutral-800/50">
                {usageData.by_provider.map((p) => (
                  <div key={p.provider} className="px-4 py-2.5 flex items-center justify-between">
                    <span className="text-sm text-neutral-300 capitalize">{p.provider}</span>
                    <div className="flex items-center gap-4 text-xs text-neutral-500">
                      <span>{fmtNum(p.tokens)} tokens</span>
                      <span>{p.requests} req</span>
                      <span className="text-neutral-300">${p.cost_usd.toFixed(4)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* User management */}
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-neutral-800">
            <Users className="w-4 h-4 text-neutral-500" />
            <h2 className="text-sm font-medium text-neutral-300">Users</h2>
            <span className="ml-auto text-xs text-neutral-600">{usersPage?.total ?? "…"} total</span>
          </div>

          {/* Search */}
          <div className="px-4 py-3 border-b border-neutral-800/50">
            <form
              onSubmit={(e) => { e.preventDefault(); setSearch(searchInput); setPage(1); }}
              className="flex items-center gap-2"
            >
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-neutral-600" />
                <input
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  placeholder="Search by email or username…"
                  className="w-full pl-8 pr-3 py-2 bg-neutral-800 rounded-lg text-sm text-neutral-200 placeholder-neutral-600 border border-neutral-700 focus:outline-none focus:border-brand-500"
                />
              </div>
              <button type="submit" className="px-3 py-2 rounded-lg bg-neutral-700 hover:bg-neutral-600 text-xs text-neutral-300 transition-colors">
                Search
              </button>
            </form>
          </div>

          {/* User rows */}
          {usersLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 text-neutral-600 animate-spin" />
            </div>
          ) : (
            <div className="divide-y divide-neutral-800/50">
              {(usersPage?.items ?? []).map((u) => (
                <div key={u.id} className="px-4 py-3 flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-neutral-800 flex items-center justify-center text-xs font-medium text-neutral-400 flex-shrink-0">
                    {(u.full_name ?? u.username).charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-neutral-200 truncate">{u.full_name ?? u.username}</p>
                    <p className="text-xs text-neutral-500 truncate">{u.email}</p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {/* Role select */}
                    <select
                      value={u.role}
                      onChange={(e) => updateUser.mutate({ id: u.id, role: e.target.value })}
                      className="text-xs bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-neutral-300 focus:outline-none focus:border-brand-500"
                    >
                      <option value="user">user</option>
                      <option value="admin">admin</option>
                    </select>
                    {/* Active toggle */}
                    <button
                      onClick={() => updateUser.mutate({ id: u.id, is_active: !u.is_active })}
                      className={cn(
                        "text-xs px-2 py-1 rounded border transition-colors",
                        u.is_active
                          ? "text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/10"
                          : "text-red-400 border-red-500/30 hover:bg-red-500/10"
                      )}
                    >
                      {u.is_active ? "Active" : "Inactive"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {(usersPage?.total ?? 0) > 20 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-neutral-800">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={!usersPage?.has_prev}
                className="p-1.5 rounded text-neutral-500 hover:text-neutral-200 disabled:opacity-30 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-xs text-neutral-600">
                Page {page} of {Math.ceil((usersPage?.total ?? 0) / 20)}
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={!usersPage?.has_next}
                className="p-1.5 rounded text-neutral-500 hover:text-neutral-200 disabled:opacity-30 transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-4">
      <div className="flex items-center gap-2 mb-2 text-neutral-500">{icon}<span className="text-xs">{label}</span></div>
      <p className="text-xl font-semibold text-neutral-100">{value}</p>
      {sub && <p className="text-xs text-neutral-600 mt-0.5">{sub}</p>}
    </div>
  );
}
