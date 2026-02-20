export type JournalTree = Array<{
  year: number;
  months: Array<{ month: number; days: string[] }>;
}>;

export type ProposalResponse = {
  session_id: number;
  operation_id: number;
  resolved_date: string;
  action: "noop" | "append" | "update" | "create";
  reason: string;
  diff_text: string;
  proposed_entries: Array<{
    id?: number;
    sequence_no: number;
    event_text_sl: string;
    source_user_text: string;
  }>;
  warnings?: string[];
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status}: ${text}`);
  }
  return (await response.json()) as T;
}

export const api = {
  register: (email: string, password: string, timezone: string) =>
    req("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, timezone })
    }),
  login: (email: string, password: string) =>
    req("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    }),
  me: () => req<{ id: number; email: string; timezone: string }>("/api/auth/me"),
  latest: () => req<{ day_date: string | null; content: string }>("/api/journal/latest"),
  tree: () => req<{ tree: JournalTree }>("/api/journal/tree"),
  dayFile: (dayDate: string) => req<{ day_date: string; content: string }>(`/api/journal/days/${dayDate}`),
  propose: (text: string, sessionId?: number, instruction?: string) =>
    req<ProposalResponse>("/api/journal/propose", {
      method: "POST",
      body: JSON.stringify({ text, session_id: sessionId, instruction })
    }),
  confirm: (sessionId: number, idempotencyKey: string) =>
    req<{ status: string; day_date: string; final_content: string }>("/api/journal/confirm", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, idempotency_key: idempotencyKey })
    }),
  cancel: (sessionId: number) =>
    req<{ status: string; session_id: number }>("/api/journal/cancel", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId })
    })
};
