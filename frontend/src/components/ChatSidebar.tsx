"use client";

import { useState, type FormEvent } from "react";
import * as api from "@/lib/api";
import type { BoardData } from "@/lib/kanban";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type ChatSidebarProps = {
  onBoardUpdate: (board: BoardData) => void;
  onOpenChange?: (isOpen: boolean) => void;
};

export const ChatSidebar = ({ onBoardUpdate, onOpenChange }: ChatSidebarProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = () => {
    setIsOpen(true);
    onOpenChange?.(true);
  };

  const close = () => {
    setIsOpen(false);
    onOpenChange?.(false);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = input.trim();
    if (!message || isSending) {
      return;
    }

    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setInput("");
    setIsSending(true);
    setError(null);

    try {
      const { reply, board } = await api.sendChatMessage(message);
      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
      onBoardUpdate(board);
    } catch {
      setError("Something went wrong sending that message.");
    } finally {
      setIsSending(false);
    }
  };

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={open}
        className="fixed bottom-6 right-6 rounded-full bg-[var(--secondary-purple)] px-5 py-3 text-xs font-semibold uppercase tracking-wide text-white shadow-[var(--shadow)] transition hover:brightness-110"
      >
        Ask AI
      </button>
    );
  }

  return (
    <aside className="fixed bottom-6 right-6 flex h-[520px] w-[360px] flex-col overflow-hidden rounded-[28px] border border-[var(--stroke)] bg-white/95 shadow-[var(--shadow)] backdrop-blur">
      <div className="flex items-center justify-between border-b border-[var(--stroke)] px-5 py-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
            Assistant
          </p>
          <p className="mt-1 font-display text-base font-semibold text-[var(--navy-dark)]">Ask AI</p>
        </div>
        <button
          type="button"
          onClick={close}
          aria-label="Close chat"
          className="rounded-full border border-transparent px-2 py-1 text-xs font-semibold text-[var(--gray-text)] transition hover:border-[var(--stroke)] hover:text-[var(--navy-dark)]"
        >
          Close
        </button>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
        {messages.length === 0 ? (
          <p className="text-sm text-[var(--gray-text)]">
            Ask me to create, edit, or move cards — or just ask a question about the board.
          </p>
        ) : (
          messages.map((message, index) => (
            <div
              key={index}
              className={
                message.role === "user"
                  ? "ml-auto max-w-[85%] rounded-2xl bg-[var(--secondary-purple)] px-4 py-2 text-sm text-white"
                  : "mr-auto max-w-[85%] rounded-2xl bg-[var(--surface)] px-4 py-2 text-sm text-[var(--navy-dark)]"
              }
            >
              {message.content}
            </div>
          ))
        )}
        {isSending ? <p className="text-xs text-[var(--gray-text)]">Thinking…</p> : null}
        {error ? <p className="text-xs font-semibold text-red-600">{error}</p> : null}
      </div>

      <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-[var(--stroke)] p-4">
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask the assistant…"
          aria-label="Chat message"
          className="flex-1 rounded-full border border-[var(--stroke)] bg-white px-4 py-2 text-sm text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
        />
        <button
          type="submit"
          disabled={isSending}
          className="rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110 disabled:opacity-60"
        >
          Send
        </button>
      </form>
    </aside>
  );
};
