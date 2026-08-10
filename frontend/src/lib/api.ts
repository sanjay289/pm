import type { BoardData } from "@/lib/kanban";

export class UnauthorizedError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (response.status === 401) {
    throw new UnauthorizedError();
  }
  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export function fetchBoard(): Promise<BoardData> {
  return request<BoardData>("/api/board");
}

export function renameColumn(columnId: string, title: string): Promise<BoardData> {
  return request<BoardData>(`/api/columns/${columnId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export function createCard(columnId: string, title: string, details: string): Promise<BoardData> {
  return request<BoardData>("/api/cards", {
    method: "POST",
    body: JSON.stringify({ column_id: columnId, title, details }),
  });
}

export function moveCard(cardId: string, columnId: string, position: number): Promise<BoardData> {
  return request<BoardData>(`/api/cards/${cardId}`, {
    method: "PATCH",
    body: JSON.stringify({ column_id: columnId, position }),
  });
}

export function deleteCard(cardId: string): Promise<BoardData> {
  return request<BoardData>(`/api/cards/${cardId}`, { method: "DELETE" });
}

export type ChatResponse = {
  reply: string;
  board: BoardData;
};

export function sendChatMessage(message: string): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}
