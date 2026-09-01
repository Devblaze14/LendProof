// Local development sets VITE_API_BASE_URL. On Vercel, same-origin rewrites
// send /api/v1 requests to the FastAPI function without a separate API host.
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export type Role = "operator" | "reviewer" | "consumer";

export interface Session {
  accessToken: string;
  role: Role;
  name?: string;
}

const SESSION_KEY = "loan_copilot_session";

// NOTE: sessionStorage, not localStorage — deliberate choice for a demo/dev
// auth token, and fine here since this is our own local JWT, not a
// long-lived Supabase session that a real deployment would manage
// differently via the Supabase client SDK.
export function saveSession(session: Session) {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
}
export function getSession(): Session | null {
  const raw = sessionStorage.getItem(SESSION_KEY);
  return raw ? JSON.parse(raw) : null;
}
export function clearSession() {
  sessionStorage.removeItem(SESSION_KEY);
}

interface ApiErrorShape {
  error: { code: string; message: string; field?: string | null; request_id?: string };
}

export class ApiError extends Error {
  code: string;
  field?: string | null;
  constructor(shape: ApiErrorShape) {
    super(shape.error.message);
    this.code = shape.error.code;
    this.field = shape.error.field;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const session = getSession();
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };
  if (!(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (session) headers["Authorization"] = `Bearer ${session.accessToken}`;

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(body as ApiErrorShape);
  return body as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; role: Role; name?: string }>("/api/v1/auth/login", {
      method: "POST", body: JSON.stringify({ email, password }),
    }),
  guest: () =>
    request<{ access_token: string; role: Role; name?: string }>("/api/v1/auth/guest", {
      method: "POST",
    }),
  summary: () => request<{
    total_loans: number; open_exceptions: number; resolved_exceptions: number;
    verified_records: number; data_quality_score: number;
  }>("/api/v1/summary"),
  listExceptions: (params: { status?: string; severity?: string; q?: string } = {}) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    return request<Array<{
      id: string; loan_record_id: string; rule_key: string; severity: string;
      status: string; field: string | null; detail: { message?: string }; created_at: string;
    }>>(`/api/v1/exceptions${qs ? `?${qs}` : ""}`);
  },
  requestAIReview: (exceptionId: string) =>
    request<{ id: string; model: string; response_json: Record<string, unknown>; confidence: number }>(
      `/api/v1/exceptions/${exceptionId}/ai-review`, { method: "POST" }
    ),
  summarizeBatch: (status = "open") => request<{
    summary: string; top_severity: string; recommended_focus: string;
  }>(`/api/v1/ai/summarize-batch?status=${encodeURIComponent(status)}`, { method: "POST" }),
  listExceptionComments: (exceptionId: string) => request<Array<{
    id: string; exception_id: string; author_id: string | null; body: string; created_at: string;
  }>>(`/api/v1/exceptions/${exceptionId}/comments`),
  addExceptionComment: (exceptionId: string, body: string) =>
    request<{ status: string }>(`/api/v1/exceptions/${exceptionId}/comments`, {
      method: "POST", body: JSON.stringify({ body }),
    }),
  submitDecision: (exceptionId: string, action: string, aiRecommendationId?: string) =>
    request<{ status: string }>(`/api/v1/exceptions/${exceptionId}/decision`, {
      method: "POST", body: JSON.stringify({ action, ai_recommendation_id: aiRecommendationId }),
    }),
  uploadFile: (file: File, sourceType: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("source_type", sourceType);
    return request<{ id: string; status: string; row_count: number | null }>("/api/v1/uploads", {
      method: "POST", body: form,
    });
  },
  listVerified: () =>
    request<Array<{ id: string; loan_record_id: string; record_hash: string; verified_at: string }>>(
      "/api/v1/verified-loans"
    ),
  auditTrail: (loanRecordId: string) =>
    request<Array<{ id: string; event_type: string; created_at: string; detail: Record<string, unknown> }>>(
      `/api/v1/audit/${loanRecordId}`
    ),
  verifyIntegrity: (verifiedId: string) =>
    request<{ valid: boolean; broken_at_index: number | null; chain_length: number }>(
      `/api/v1/verified-loans/${verifiedId}/verify-integrity`
    ),
};
