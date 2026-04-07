"use client";

import React, { useRef, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquarePlus,
  Search,
  Pin,
  Pencil,
  Download,
  Trash2,
  MoreHorizontal,
  Sparkles,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Brain,
  X,
  BarChart2,
  Bot,
  Building2,
  Shield,
} from "lucide-react";
import { MemoryPanel } from "@/components/memory/MemoryPanel";
import { cn, formatChatTime } from "@/lib/utils";
import {
  useConversations,
  useNewChat,
  useDeleteConversation,
  useUpdateConversation,
} from "@/hooks/useConversations";
import { useAuthStore } from "@/store/auth";
import { useChatStore } from "@/store/chat";
import { conversationService } from "@/services/conversation.service";
import type { ConversationListItem } from "@/types/api";

interface SidebarProps {
  /** Mobile only — called when the X close button is pressed */
  onClose?: () => void;
}

export function Sidebar({ onClose }: SidebarProps = {}) {
  const [collapsed, setCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showSearch, setShowSearch] = useState(false);
  const [showMemory, setShowMemory] = useState(false);
  const { data: conversations, isLoading } = useConversations();
  const { mutate: deleteConversation } = useDeleteConversation();
  const { mutate: updateConversation } = useUpdateConversation();
  const { user, logout } = useAuthStore();
  const setSidebarOpen = useChatStore((s) => s.setSidebarOpen);
  const pathname = usePathname();
  const router = useRouter();

  const activeId = pathname.split("/")[1];
  const { newChat, isPending: isCreating } = useNewChat(activeId || undefined);

  const filteredConversations = conversations?.filter((c) =>
    c.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const pinnedConversations = filteredConversations?.filter((c) => c.is_pinned);
  const regularConversations = filteredConversations?.filter((c) => !c.is_pinned);

  // On mobile (rendered as overlay), never use collapsed mode
  const isMobileOverlay = !!onClose;
  const isCollapsed = isMobileOverlay ? false : collapsed;

  // On mobile overlay, close sidebar before navigating
  const navigate = (href: string) => {
    if (isMobileOverlay) setSidebarOpen(false);
    router.push(href);
  };

  return (
    <motion.aside
      animate={{ width: isCollapsed ? 56 : 260 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      className="relative flex flex-col h-full bg-neutral-900 border-r border-neutral-800 overflow-hidden"
    >
      <AnimatePresence>
        {showMemory && <MemoryPanel onClose={() => setShowMemory(false)} />}
      </AnimatePresence>

      {/* Desktop collapse toggle — hidden on mobile overlay */}
      {!isMobileOverlay && (
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="absolute -right-3 top-6 z-10 w-6 h-6 bg-neutral-800 border border-neutral-700 rounded-full flex items-center justify-center text-neutral-400 hover:text-neutral-200 transition-colors"
        >
          {collapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronLeft className="w-3 h-3" />}
        </button>
      )}

      {/* Header */}
      <div className="flex-shrink-0 p-3 space-y-2">
        {/* Logo row + mobile close button */}
        <div className="flex items-center gap-2 px-1 py-1">
          <div className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center flex-shrink-0">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          {!isCollapsed && (
            <span className="font-semibold text-neutral-100 text-sm flex-1">Lumina</span>
          )}
          {/* Mobile close button */}
          {isMobileOverlay && (
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-neutral-500 hover:text-neutral-200 hover:bg-neutral-800 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* New chat button */}
        <button
          onClick={() => { if (isMobileOverlay) setSidebarOpen(false); newChat(); }}
          disabled={isCreating}
          className={cn(
            "w-full flex items-center gap-2 rounded-xl transition-all",
            "bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 hover:border-neutral-600",
            isCollapsed ? "p-2 justify-center" : "px-3 py-2"
          )}
          title="New conversation"
        >
          <MessageSquarePlus className="w-4 h-4 text-neutral-300 flex-shrink-0" />
          {!isCollapsed && (
            <span className="text-sm text-neutral-300">New chat</span>
          )}
        </button>

        {/* Search */}
        {!isCollapsed && (
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-neutral-500" />
            <input
              type="text"
              placeholder="Search chats..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 bg-neutral-800 border border-neutral-700 rounded-lg text-xs text-neutral-300 placeholder:text-neutral-600 outline-none focus:border-brand-500/50"
            />
          </div>
        )}
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-neutral-800 px-2 py-1 space-y-4">
        {isLoading ? (
          <ConversationListSkeleton />
        ) : (
          <>
            {pinnedConversations && pinnedConversations.length > 0 && (
              <ConversationGroup
                label="Pinned"
                conversations={pinnedConversations}
                activeId={activeId}
                collapsed={isCollapsed}
                onNavigate={navigate}
                onPin={(id, pinned) => updateConversation({ id, is_pinned: !pinned })}
                onDelete={(id) => deleteConversation(id)}
                onRename={(id, title) => updateConversation({ id, title })}
              />
            )}
            <ConversationGroup
              label="Recent"
              conversations={regularConversations || []}
              activeId={activeId}
              collapsed={isCollapsed}
              onNavigate={navigate}
              onPin={(id, pinned) => updateConversation({ id, is_pinned: !pinned })}
              onDelete={(id) => deleteConversation(id)}
              onRename={(id, title) => updateConversation({ id, title })}
            />
          </>
        )}
      </div>

      {/* Footer */}
      <div className="flex-shrink-0 border-t border-neutral-800 p-3 space-y-1">
        {!isCollapsed && (
          <>
            <button
              onClick={() => setShowMemory(true)}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 transition-colors text-sm"
            >
              <Brain className="w-4 h-4" />
              Memory
            </button>

            <div className="pt-1 pb-0.5">
              <p className="text-xs font-medium text-neutral-600 uppercase tracking-wider px-1 mb-1">
                Tools
              </p>
              <button
                onClick={() => navigate("/usage")}
                className={cn(
                  "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg transition-colors text-sm",
                  pathname === "/usage"
                    ? "bg-neutral-800 text-neutral-200"
                    : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800"
                )}
              >
                <BarChart2 className="w-4 h-4" />
                Usage &amp; Cost
              </button>
              <button
                onClick={() => navigate("/agents")}
                className={cn(
                  "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg transition-colors text-sm",
                  pathname === "/agents"
                    ? "bg-neutral-800 text-neutral-200"
                    : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800"
                )}
              >
                <Bot className="w-4 h-4" />
                Agents
              </button>
              <button
                onClick={() => navigate("/organization")}
                className={cn(
                  "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg transition-colors text-sm",
                  pathname === "/organization"
                    ? "bg-neutral-800 text-neutral-200"
                    : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800"
                )}
              >
                <Building2 className="w-4 h-4" />
                Organization
              </button>
              {user?.role === "admin" && (
                <button
                  onClick={() => navigate("/admin")}
                  className={cn(
                    "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg transition-colors text-sm",
                    pathname === "/admin"
                      ? "bg-neutral-800 text-neutral-200"
                      : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800"
                  )}
                >
                  <Shield className="w-4 h-4" />
                  Admin
                </button>
              )}
            </div>

            <button
              onClick={() => navigate("/settings")}
              className={cn(
                "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg transition-colors text-sm",
                pathname === "/settings"
                  ? "bg-neutral-800 text-neutral-200"
                  : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800"
              )}
            >
              <Settings className="w-4 h-4" />
              Settings
            </button>
            <button
              onClick={() => { logout(); router.push("/login"); }}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-neutral-400 hover:text-red-400 hover:bg-red-500/5 transition-colors text-sm"
            >
              <LogOut className="w-4 h-4" />
              Sign out
            </button>
          </>
        )}

        {isCollapsed && (
          <>
            <button
              onClick={() => navigate("/usage")}
              title="Usage & Cost"
              className={cn(
                "w-full flex items-center justify-center p-2 rounded-lg transition-colors",
                pathname === "/usage"
                  ? "bg-neutral-800 text-neutral-200"
                  : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800"
              )}
            >
              <BarChart2 className="w-4 h-4" />
            </button>
            <button
              onClick={() => navigate("/agents")}
              title="Agents"
              className={cn(
                "w-full flex items-center justify-center p-2 rounded-lg transition-colors",
                pathname === "/agents"
                  ? "bg-neutral-800 text-neutral-200"
                  : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800"
              )}
            >
              <Bot className="w-4 h-4" />
            </button>
            <button
              onClick={() => navigate("/organization")}
              title="Organization"
              className={cn(
                "w-full flex items-center justify-center p-2 rounded-lg transition-colors",
                pathname === "/organization"
                  ? "bg-neutral-800 text-neutral-200"
                  : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800"
              )}
            >
              <Building2 className="w-4 h-4" />
            </button>
            {user?.role === "admin" && (
              <button
                onClick={() => navigate("/admin")}
                title="Admin"
                className={cn(
                  "w-full flex items-center justify-center p-2 rounded-lg transition-colors",
                  pathname === "/admin"
                    ? "bg-neutral-800 text-neutral-200"
                    : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800"
                )}
              >
                <Shield className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={() => navigate("/settings")}
              title="Settings"
              className={cn(
                "w-full flex items-center justify-center p-2 rounded-lg transition-colors",
                pathname === "/settings"
                  ? "bg-neutral-800 text-neutral-200"
                  : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800"
              )}
            >
              <Settings className="w-4 h-4" />
            </button>
            <button
              onClick={() => { logout(); router.push("/login"); }}
              title="Sign out"
              className="w-full flex items-center justify-center p-2 rounded-lg text-neutral-500 hover:text-red-400 hover:bg-red-500/5 transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </>
        )}
      </div>
    </motion.aside>
  );
}

interface ConversationGroupProps {
  label: string;
  conversations: ConversationListItem[];
  activeId: string;
  collapsed: boolean;
  onNavigate: (href: string) => void;
  onPin: (id: string, currentlyPinned: boolean) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
}

function ConversationGroup({
  label,
  conversations,
  activeId,
  collapsed,
  onNavigate,
  onPin,
  onDelete,
  onRename,
}: ConversationGroupProps) {
  if (conversations.length === 0) return null;

  return (
    <div>
      {!collapsed && (
        <p className="text-xs font-medium text-neutral-600 uppercase tracking-wider px-2 mb-1">
          {label}
        </p>
      )}
      <div className="space-y-0.5">
        {conversations.map((conv) => (
          <ConversationItem
            key={conv.id}
            conversation={conv}
            isActive={conv.id === activeId}
            collapsed={collapsed}
            onNavigate={onNavigate}
            onPin={onPin}
            onDelete={onDelete}
            onRename={onRename}
          />
        ))}
      </div>
    </div>
  );
}

function ConversationItem({
  conversation,
  isActive,
  collapsed,
  onNavigate,
  onPin,
  onDelete,
  onRename,
}: {
  conversation: ConversationListItem;
  isActive: boolean;
  collapsed: boolean;
  onNavigate: (href: string) => void;
  onPin: (id: string, pinned: boolean) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
}) {
  const [showMenu, setShowMenu] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(conversation.title);
  const renameInputRef = React.useRef<HTMLInputElement>(null);

  const startRename = (e: React.MouseEvent) => {
    e.stopPropagation();
    setRenameValue(conversation.title);
    setIsRenaming(true);
    setShowMenu(false);
    // Focus after render
    setTimeout(() => renameInputRef.current?.select(), 0);
  };

  const commitRename = () => {
    const trimmed = renameValue.trim();
    if (trimmed && trimmed !== conversation.title) {
      onRename(conversation.id, trimmed);
    }
    setIsRenaming(false);
  };

  return (
    <div
      className={cn(
        "group relative flex items-center rounded-lg transition-all",
        collapsed ? "px-2 py-2 justify-center cursor-pointer" : "px-3 py-2",
        isActive
          ? "bg-neutral-800 text-neutral-100"
          : "text-neutral-400 hover:bg-neutral-800/60 hover:text-neutral-300",
        !isRenaming && "cursor-pointer"
      )}
      onClick={() => !isRenaming && onNavigate(`/${conversation.id}`)}
      title={collapsed ? conversation.title : undefined}
    >
      <MessageSquarePlus className="w-4 h-4 flex-shrink-0" />

      {!collapsed && (
        <>
          <div className="ml-2.5 flex-1 min-w-0">
            {isRenaming ? (
              <input
                ref={renameInputRef}
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                onBlur={commitRename}
                onKeyDown={(e) => {
                  if (e.key === "Enter") commitRename();
                  if (e.key === "Escape") setIsRenaming(false);
                  e.stopPropagation();
                }}
                onClick={(e) => e.stopPropagation()}
                autoFocus
                className="w-full bg-neutral-700 border border-brand-500/50 rounded px-1.5 py-0.5 text-sm text-neutral-100 outline-none"
              />
            ) : (
              <>
                <p className="text-sm truncate">{conversation.title}</p>
                <p className="text-xs text-neutral-600 truncate">
                  {formatChatTime(conversation.last_message_at)}
                </p>
              </>
            )}
          </div>

          {/* Context menu button */}
          {!isRenaming && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowMenu(!showMenu);
              }}
              className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-neutral-700 transition-all flex-shrink-0"
            >
              <MoreHorizontal className="w-3.5 h-3.5" />
            </button>
          )}

          {/* Dropdown menu */}
          <AnimatePresence>
            {showMenu && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="absolute right-0 top-full mt-1 z-20 w-44 bg-neutral-800 border border-neutral-700 rounded-lg shadow-xl overflow-hidden"
                onMouseLeave={() => setShowMenu(false)}
              >
                <button
                  onClick={startRename}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-neutral-300 hover:bg-neutral-700"
                >
                  <Pencil className="w-3.5 h-3.5" />
                  Rename
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onPin(conversation.id, conversation.is_pinned);
                    setShowMenu(false);
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-neutral-300 hover:bg-neutral-700"
                >
                  <Pin className="w-3.5 h-3.5" />
                  {conversation.is_pinned ? "Unpin" : "Pin"}
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    conversationService.export(conversation.id, "markdown");
                    setShowMenu(false);
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-neutral-300 hover:bg-neutral-700"
                >
                  <Download className="w-3.5 h-3.5" />
                  Export (.md)
                </button>
                <div className="border-t border-neutral-700/50 mt-1 pt-1">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(conversation.id);
                      setShowMenu(false);
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Delete
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </>
      )}
    </div>
  );
}

function ConversationListSkeleton() {
  return (
    <div className="space-y-1 px-1 animate-pulse">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="h-10 bg-neutral-800 rounded-lg" />
      ))}
    </div>
  );
}
