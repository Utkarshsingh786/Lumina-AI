/**
 * Individual conversation page.
 * Renders the ChatWindow for a specific conversation ID.
 */

"use client";

import { use } from "react";
import { ChatWindow } from "@/components/chat/ChatWindow";

interface ConversationPageProps {
  params: Promise<{ id: string }>;
}

export default function ConversationPage({ params }: ConversationPageProps) {
  const { id } = use(params);
  return <ChatWindow conversationId={id} />;
}
