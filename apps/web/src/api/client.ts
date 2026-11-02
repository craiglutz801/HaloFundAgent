export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown>) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

let csrfToken = "";

export function setCsrf(token: string) {
  csrfToken = token;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const method = (init.method ?? "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD") {
    headers.set("Content-Type", "application/json");
    headers.set("X-CSRF-Token", csrfToken);
    if (!headers.has("Idempotency-Key")) headers.set("Idempotency-Key", crypto.randomUUID());
  }
  const response = await fetch(path, { ...init, headers, credentials: "same-origin" });
  const body = (await response.json()) as T & {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
  if (!response.ok) {
    throw new ApiError(response.status, body.code ?? "ERROR", body.message ?? "Request failed", body.details ?? {});
  }
  return body;
}

export async function ensureCsrf() {
  const payload = await api<{ csrf_token: string }>("/api/v1/auth/csrf");
  setCsrf(payload.csrf_token);
}
