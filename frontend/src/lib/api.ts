import type { components } from "@/lib/api-types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
export const DEMO_USER_ID = "demo-user";
export const DEMO_SESSION_ID = "demo-session";

export type QueryResult = components["schemas"]["QueryResponse"];
export type TraceEntry = components["schemas"]["TraceRoundOut"];
export type ScoredPaper = components["schemas"]["ScoredPaperOut"];
export type Condition = components["schemas"]["ConditionOut"];
export type ContrastPaper = components["schemas"]["ContrastPaperOut"];
export type DemoContrast = components["schemas"]["DemoContrastResponse"];
export type MemoryProfile = components["schemas"]["ProfileOut"];
export type EconomicsSummary = components["schemas"]["EconomicsSummaryOut"];
export type EconomicsAnswer = components["schemas"]["EconomicsAskOut"];
export type EconomicsRequest = components["schemas"]["EconomicsRequestOut"];

export type PortHealth = { ok: boolean; detail: string };
export type Health = {
  status: string;
  ports: Record<"retrieval" | "llm" | "memory" | "ledger", PortHealth>;
};

async function request<T>(path: string, init?: RequestInit, timeoutMs = 10000): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!response.ok) throw new Error(`Request to ${path} failed with status ${response.status}`);
  return response.status === 204 ? (undefined as T) : (response.json() as Promise<T>);
}

function post<T>(path: string, body: unknown, timeoutMs?: number): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) }, timeoutMs);
}

export function queryLiterature(query: string, personalize = true): Promise<QueryResult> {
  return post<QueryResult>(
    "/query",
    { query, session_id: DEMO_SESSION_ID, user_id: DEMO_USER_ID, personalize },
    170000,
  );
}

export function queryLiteratureStream(
  query: string,
  personalize: boolean,
  onStage: (stage: string, detail: { iteration?: number }) => void,
): Promise<QueryResult> {
  return new Promise((resolve, reject) => {
    void (async () => {
      let response: Response;
      try {
        response = await fetch(`${API_BASE_URL}/query/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query,
            session_id: DEMO_SESSION_ID,
            user_id: DEMO_USER_ID,
            personalize,
          }),
          signal: AbortSignal.timeout(170000),
        });
      } catch (error) {
        reject(error);
        return;
      }
      if (!response.ok || !response.body) {
        reject(new Error(`Request to /query/stream failed with status ${response.status}`));
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let separatorIndex = buffer.indexOf("\n\n");
          while (separatorIndex !== -1) {
            const line = buffer.slice(0, separatorIndex).trim();
            buffer = buffer.slice(separatorIndex + 2);
            if (line.startsWith("data:")) {
              const payload = JSON.parse(line.slice(5).trim());
              if (payload.type === "stage") onStage(payload.stage, { iteration: payload.iteration });
              if (payload.type === "done") {
                resolve(payload.result as QueryResult);
                return;
              }
              if (payload.type === "error") {
                reject(new Error(payload.message));
                return;
              }
            }
            separatorIndex = buffer.indexOf("\n\n");
          }
        }
        reject(new Error("Stream ended without a result"));
      } catch (error) {
        reject(error);
      }
    })();
  });
}

export function getMemoryProfile(): Promise<MemoryProfile> {
  return request<MemoryProfile>(`/memory/profile?user_id=${DEMO_USER_ID}`);
}

export function setMemorySpecialty(specialty: string): Promise<void> {
  return post<void>("/memory/specialty", { user_id: DEMO_USER_ID, specialty });
}

export function forgetMemory(): Promise<void> {
  return post<void>("/memory/forget", { user_id: DEMO_USER_ID });
}

export function getEconomicsSummary(window = "24h"): Promise<EconomicsSummary> {
  return request<EconomicsSummary>(`/economics/summary?window=${encodeURIComponent(window)}`);
}

export function getEconomicsRequest(requestId: string): Promise<EconomicsRequest> {
  return request<EconomicsRequest>(`/economics/request/${encodeURIComponent(requestId)}`);
}

export function askEconomics(question: string): Promise<EconomicsAnswer> {
  return post<EconomicsAnswer>("/economics/ask", { question }, 30000);
}

export async function getHealth(): Promise<Health> {
  const raw = (await request<Record<string, unknown>>("/health")) as {
    status?: unknown;
    ports?: Record<string, { ok?: unknown; detail?: unknown }>;
  };
  const names = ["retrieval", "llm", "memory", "ledger"] as const;
  return {
    status: typeof raw.status === "string" ? raw.status : "unknown",
    ports: Object.fromEntries(
      names.map((name) => [
        name,
        {
          ok: raw.ports?.[name]?.ok === true,
          detail: typeof raw.ports?.[name]?.detail === "string" ? raw.ports[name].detail : "No status",
        },
      ]),
    ) as Health["ports"],
  };
}

export function getDemoContrast(): Promise<DemoContrast> {
  return request<DemoContrast>("/demo-contrast", undefined, 15000);
}

export function getConditions(): Promise<Condition[]> {
  return request<Condition[]>("/conditions");
}

export function getAtlasUrl(conditionName: string): string {
  return `${API_BASE_URL}/atlas/${encodeURIComponent(conditionName)}`;
}

export function getDefaultAtlasUrl(): string {
  return `${API_BASE_URL}/atlas`;
}

export function getAtlasQueryUrl(conditionNames: string[]): string {
  const params = new URLSearchParams({ conditions: conditionNames.join(",") });
  return `${API_BASE_URL}/atlas/query?${params.toString()}`;
}
