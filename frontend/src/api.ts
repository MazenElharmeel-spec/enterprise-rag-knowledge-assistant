export const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1';

export type User = { id: string; email: string; full_name: string; role: string };
export type Document = {
  id: string;
  title: string;
  filename: string;
  visibility: string;
  status: string;
  stage_error?: string | null;
  current_version: number;
  created_at: string;
};
export type Citation = {
  marker: number;
  id: string;
  document_id: string;
  title: string;
  page_start: number | null;
  page_end: number | null;
  heading_path: string[];
  snippet: string;
  score: number;
  url: string;
};
export type ChatResult = {
  answer: string;
  citations: Citation[];
  conversationId: string;
  messageId: string;
};

export function token(): string | null {
  return localStorage.getItem('access_token');
}
export function clearAuth(): void {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const access = token();
  if (access) headers.set('Authorization', `Bearer ${access}`);
  const response = await fetch(`${API}${path}`, { ...init, headers });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function ask(
  question: string,
  conversationId?: string,
  deepSearch = false,
  onToken?: (token: string) => void,
): Promise<ChatResult> {
  const response = await fetch(`${API}/chat/ask`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token()}`,
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({ question, conversation_id: conversationId, deep_search: deepSearch }),
  });
  if (!response.ok || !response.body) throw new Error('Could not start the answer stream');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let answerText = '';
  let citations: Citation[] = [];
  let currentEvent = '';
  let conversation = conversationId ?? '';
  let messageId = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';
    for (const block of events) {
      for (const line of block.split('\n')) {
        if (line.startsWith('event: ')) currentEvent = line.slice(7);
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6);
        if (currentEvent === 'meta') {
          const meta = JSON.parse(data) as { conversation_id: string; message_id: string };
          conversation = meta.conversation_id;
          messageId = meta.message_id;
        } else if (currentEvent === 'token') {
          const piece = (JSON.parse(data) as { text: string }).text;
          answerText += piece;
          onToken?.(piece);
        } else if (currentEvent === 'citations') citations = JSON.parse(data) as Citation[];
      }
    }
  }
  return { answer: answerText, citations, conversationId: conversation, messageId };
}
