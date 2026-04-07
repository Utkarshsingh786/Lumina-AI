"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  Users,
  Plus,
  Link,
  Trash2,
  Crown,
  Shield,
  UserMinus,
  Loader2,
  Menu,
  ChevronRight,
  Copy,
  Check,
} from "lucide-react";
import toast from "react-hot-toast";
import { apiClient } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { useChatStore } from "@/store/chat";
import { cn } from "@/lib/utils";
import type { Organization, OrganizationDetail } from "@/types/api";

// ── API helpers ────────────────────────────────────────
const fetchMyOrgs = async (): Promise<Organization[]> => (await apiClient.get("/orgs")).data;
const fetchOrgDetail = async (id: string): Promise<OrganizationDetail> => (await apiClient.get(`/orgs/${id}`)).data;

export default function OrganizationPage() {
  const { user } = useAuthStore();
  const toggleSidebar = useChatStore((s) => s.toggleSidebar);
  const queryClient = useQueryClient();
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newOrgName, setNewOrgName] = useState("");
  const [newOrgDesc, setNewOrgDesc] = useState("");
  const [joinToken, setJoinToken] = useState("");
  const [joiningMode, setJoiningMode] = useState(false);
  const [copied, setCopied] = useState(false);

  const { data: orgs = [], isLoading } = useQuery({ queryKey: ["orgs"], queryFn: fetchMyOrgs, staleTime: 30_000 });
  const { data: orgDetail } = useQuery({
    queryKey: ["org", selectedOrgId],
    queryFn: () => fetchOrgDetail(selectedOrgId!),
    enabled: !!selectedOrgId,
    staleTime: 30_000,
  });

  const createOrg = useMutation({
    mutationFn: (data: { name: string; description?: string }) => apiClient.post("/orgs", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orgs"] });
      setCreating(false);
      setNewOrgName("");
      setNewOrgDesc("");
      toast.success("Organisation created");
    },
    onError: () => toast.error("Failed to create organisation"),
  });

  const generateInvite = useMutation({
    mutationFn: (orgId: string) => apiClient.post(`/orgs/${orgId}/invite`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org", selectedOrgId] });
      toast.success("Invite link generated");
    },
    onError: () => toast.error("Failed to generate invite"),
  });

  const joinOrg = useMutation({
    mutationFn: (token: string) => apiClient.post(`/orgs/join/${token}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orgs"] });
      setJoiningMode(false);
      setJoinToken("");
      toast.success("Joined organisation!");
    },
    onError: (e: unknown) => toast.error((e as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Invalid or expired token"),
  });

  const removeMember = useMutation({
    mutationFn: ({ orgId, userId }: { orgId: string; userId: string }) =>
      apiClient.delete(`/orgs/${orgId}/members/${userId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org", selectedOrgId] });
      toast.success("Member removed");
    },
    onError: () => toast.error("Failed to remove member"),
  });

  const deleteOrg = useMutation({
    mutationFn: (orgId: string) => apiClient.delete(`/orgs/${orgId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orgs"] });
      setSelectedOrgId(null);
      toast.success("Organisation deleted");
    },
    onError: () => toast.error("Failed to delete organisation"),
  });

  const copyInvite = async () => {
    const token = orgDetail?.invite_token;
    if (!token) return;
    const link = `${window.location.origin}/orgs/join/${token}`;
    await navigator.clipboard.writeText(link);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    toast.success("Invite link copied");
  };

  const myRole = orgDetail?.members.find((m) => m.user_id === user?.id)?.role;

  const ROLE_ICON: Record<string, React.ReactNode> = {
    owner: <Crown className="w-3 h-3 text-amber-400" />,
    admin: <Shield className="w-3 h-3 text-blue-400" />,
    member: <Users className="w-3 h-3 text-neutral-500" />,
  };

  return (
    <div className="flex flex-col h-full overflow-y-auto bg-neutral-950 scrollbar-thin scrollbar-thumb-neutral-800">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-neutral-800 md:hidden">
        <button onClick={toggleSidebar} className="p-1.5 rounded-lg text-neutral-500 hover:text-neutral-200 hover:bg-neutral-800 transition-colors">
          <Menu className="w-5 h-5" />
        </button>
        <h1 className="text-sm font-semibold text-neutral-200">Organizations</h1>
      </div>

      <div className="max-w-3xl mx-auto w-full px-4 py-8 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-neutral-100 flex items-center gap-2">
              <Building2 className="w-5 h-5 text-neutral-400" /> Organizations
            </h1>
            <p className="text-sm text-neutral-500 mt-0.5">Collaborate with your team</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setJoiningMode((v) => !v)}
              className="text-xs px-3 py-2 rounded-lg border border-neutral-700 text-neutral-400 hover:text-neutral-200 hover:border-neutral-600 transition-colors"
            >
              Join
            </button>
            <button
              onClick={() => setCreating((v) => !v)}
              className="flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white transition-colors"
            >
              <Plus className="w-3.5 h-3.5" /> New
            </button>
          </div>
        </div>

        {/* Join form */}
        {joiningMode && (
          <div className="rounded-xl border border-neutral-700 bg-neutral-900 p-4">
            <h3 className="text-sm font-medium text-neutral-200 mb-3">Join with invite token</h3>
            <div className="flex gap-2">
              <input
                value={joinToken}
                onChange={(e) => setJoinToken(e.target.value)}
                placeholder="Paste invite token…"
                className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-brand-500"
              />
              <button
                onClick={() => joinOrg.mutate(joinToken.trim())}
                disabled={!joinToken.trim() || joinOrg.isPending}
                className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-sm disabled:opacity-50 transition-colors"
              >
                {joinOrg.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : "Join"}
              </button>
            </div>
          </div>
        )}

        {/* Create form */}
        {creating && (
          <div className="rounded-xl border border-neutral-700 bg-neutral-900 p-4">
            <h3 className="text-sm font-medium text-neutral-200 mb-3">New organisation</h3>
            <div className="space-y-3">
              <input
                value={newOrgName}
                onChange={(e) => setNewOrgName(e.target.value)}
                placeholder="Organisation name *"
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-brand-500"
              />
              <input
                value={newOrgDesc}
                onChange={(e) => setNewOrgDesc(e.target.value)}
                placeholder="Description (optional)"
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-brand-500"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => createOrg.mutate({ name: newOrgName.trim(), description: newOrgDesc.trim() || undefined })}
                  disabled={!newOrgName.trim() || createOrg.isPending}
                  className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-sm disabled:opacity-50 transition-colors"
                >
                  {createOrg.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : "Create"}
                </button>
                <button onClick={() => setCreating(false)} className="px-4 py-2 rounded-lg text-neutral-500 hover:text-neutral-300 text-sm transition-colors">
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Org list */}
        {isLoading ? (
          <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 text-neutral-600 animate-spin" /></div>
        ) : orgs.length === 0 ? (
          <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 px-6 py-12 text-center">
            <Building2 className="w-8 h-8 text-neutral-700 mx-auto mb-3" />
            <p className="text-sm text-neutral-500">You don't belong to any organisations yet.</p>
            <p className="text-xs text-neutral-600 mt-1">Create one or ask a teammate for an invite link.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {orgs.map((org) => (
              <div key={org.id} className="rounded-xl border border-neutral-800 bg-neutral-900/60 overflow-hidden">
                <button
                  onClick={() => setSelectedOrgId(selectedOrgId === org.id ? null : org.id)}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-neutral-800/40 transition-colors text-left"
                >
                  <div className="w-9 h-9 rounded-xl bg-brand-600/20 border border-brand-500/20 flex items-center justify-center text-brand-400 font-semibold text-sm flex-shrink-0">
                    {org.name.charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-neutral-200 truncate">{org.name}</p>
                    {org.description && <p className="text-xs text-neutral-500 truncate">{org.description}</p>}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-neutral-600 flex-shrink-0">
                    <Users className="w-3.5 h-3.5" />
                    <span>{org.member_count}</span>
                  </div>
                  <ChevronRight className={cn("w-4 h-4 text-neutral-600 transition-transform", selectedOrgId === org.id && "rotate-90")} />
                </button>

                {selectedOrgId === org.id && orgDetail && orgDetail.id === org.id && (
                  <div className="border-t border-neutral-800">
                    {/* Invite section — visible to owners/admins */}
                    {myRole && ["owner", "admin"].includes(myRole) && (
                      <div className="px-4 py-3 border-b border-neutral-800/50">
                        <p className="text-xs font-medium text-neutral-400 mb-2">Invite link</p>
                        {orgDetail.invite_token ? (
                          <div className="flex items-center gap-2">
                            <div className="flex-1 bg-neutral-800 rounded-lg px-3 py-1.5 text-xs text-neutral-400 truncate font-mono">
                              {`${window.location.origin}/orgs/join/${orgDetail.invite_token}`}
                            </div>
                            <button onClick={copyInvite} className="p-2 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-400 transition-colors">
                              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => generateInvite.mutate(org.id)}
                            disabled={generateInvite.isPending}
                            className="flex items-center gap-2 text-xs px-3 py-2 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-400 transition-colors"
                          >
                            <Link className="w-3.5 h-3.5" /> Generate invite link
                          </button>
                        )}
                        {orgDetail.invite_expires_at && (
                          <p className="text-xs text-neutral-600 mt-1">
                            Expires {new Date(orgDetail.invite_expires_at).toLocaleDateString()}
                          </p>
                        )}
                      </div>
                    )}

                    {/* Member list */}
                    <div className="divide-y divide-neutral-800/40">
                      {orgDetail.members.map((m) => (
                        <div key={m.user_id} className="flex items-center gap-3 px-4 py-2.5">
                          <div className="w-7 h-7 rounded-full bg-neutral-800 flex items-center justify-center text-xs text-neutral-500 flex-shrink-0">
                            {(m.full_name ?? m.username).charAt(0).toUpperCase()}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-neutral-300 truncate">{m.full_name ?? m.username}</p>
                            <p className="text-xs text-neutral-600 truncate">{m.email}</p>
                          </div>
                          <div className="flex items-center gap-1.5 text-xs text-neutral-500 flex-shrink-0">
                            {ROLE_ICON[m.role]}
                            <span className="capitalize">{m.role}</span>
                          </div>
                          {myRole && ["owner", "admin"].includes(myRole) && m.user_id !== user?.id && m.role !== "owner" && (
                            <button
                              onClick={() => removeMember.mutate({ orgId: org.id, userId: m.user_id })}
                              className="p-1.5 rounded text-neutral-600 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                              title="Remove member"
                            >
                              <UserMinus className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      ))}
                    </div>

                    {/* Delete org — owner only */}
                    {myRole === "owner" && (
                      <div className="px-4 py-3 border-t border-neutral-800/50">
                        <button
                          onClick={() => {
                            if (window.confirm(`Delete "${org.name}"? This cannot be undone.`)) {
                              deleteOrg.mutate(org.id);
                            }
                          }}
                          className="flex items-center gap-2 text-xs text-red-400 hover:text-red-300 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" /> Delete organisation
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
