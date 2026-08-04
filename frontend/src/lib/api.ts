// frontend/src/lib/api.ts
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type TraceEntry = {
  iteration: number;
  retrieved_pmids: string[];
  relevant: boolean;
  confidence: number;
  note: string;
};

export type Citation = {
  marker: string;
  pmid: string;
  title: string;
  condition: string;
};

export type SuggestedCondition = {
  name: string;
  paper_count: number;
};

export type CaseContext = {
  condition_name: string;
  rarity: string;
  region_literature: string;
  atlas_label: string;
  corpus_paper_count: number;
  imaging_findings: string | null;
  teaching_point: string | null;
};

export type DifferentialItem = {
  condition_name: string;
  marker: string;
  pmid: string;
};

export type FlaggedClaim = {
  sentence: string;
  marker: string | null;
  status: string;
  reason: string;
};

export type QueryResult = {
  summary_text: string;
  citations: Citation[];
  trace: TraceEntry[];
  low_confidence: boolean;
  degraded: boolean;
  no_match: boolean;
  too_generic: boolean;
  example_query: string | null;
  suggested_conditions: SuggestedCondition[];
  flagged_claims: FlaggedClaim[];
  case_context: CaseContext | null;
  differential: DifferentialItem[];
};

export type ContrastPaper = {
  pmid: string;
  title: string;
  condition: string;
  rarity: "rare" | "common";
};

export type DemoContrast = {
  query: string;
  naive: ContrastPaper[];
  weighted: ContrastPaper[];
  rare_case_pmid: string;
};

export type Condition = {
  name: string;
  rarity: "rare" | "common";
  region_literature: string;
  atlas_label: string;
  overlaps_with: string[];
};

function timeoutSignal(timeoutMs: number): AbortSignal {
  const controller = new AbortController();
  setTimeout(() => controller.abort(), timeoutMs);
  return controller.signal;
}

async function postJson<T>(path: string, body: unknown, timeoutMs = 45000): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: timeoutSignal(timeoutMs),
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`Request to ${path} timed out after ${timeoutMs}ms`);
    }
    throw err;
  }
  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function getJson<T>(path: string, timeoutMs = 10000, retries = 0): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { signal: timeoutSignal(timeoutMs) });
  } catch (err) {
    if (retries > 0) {
      await new Promise((resolve) => setTimeout(resolve, 500));
      return getJson<T>(path, timeoutMs, retries - 1);
    }
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`Request to ${path} timed out after ${timeoutMs}ms`);
    }
    throw err;
  }
  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function queryLiterature(query: string): Promise<QueryResult> {
  return postJson<QueryResult>("/query", { query }, 170000);
}

export function queryLiteratureStream(
  query: string,
  onStage: (stage: string, detail: { iteration?: number }) => void,
): Promise<QueryResult> {
  return new Promise((resolve, reject) => {
    (async () => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 170000);
      let response: Response;
      try {
        response = await fetch(`${API_BASE_URL}/query/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query }),
          signal: controller.signal,
        });
      } catch (err) {
        clearTimeout(timeoutId);
        if (err instanceof DOMException && err.name === "AbortError") {
          reject(new Error("Request to /query/stream timed out after 170000ms"));
          return;
        }
        reject(err);
        return;
      }
      if (!response.ok || !response.body) {
        clearTimeout(timeoutId);
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

          let separatorIndex: number;
          while ((separatorIndex = buffer.indexOf("\n\n")) !== -1) {
            const frame = buffer.slice(0, separatorIndex);
            buffer = buffer.slice(separatorIndex + 2);
            const line = frame.trim();
            if (!line.startsWith("data:")) continue;
            const payload = JSON.parse(line.slice(5).trim());

            if (payload.type === "stage") {
              onStage(payload.stage, { iteration: payload.iteration });
            } else if (payload.type === "done") {
              clearTimeout(timeoutId);
              resolve(payload.result as QueryResult);
              return;
            } else if (payload.type === "error") {
              clearTimeout(timeoutId);
              reject(new Error(payload.message));
              return;
            }
          }
        }
        clearTimeout(timeoutId);
        reject(new Error("Stream ended without a done or error event"));
      } catch (err) {
        clearTimeout(timeoutId);
        if (err instanceof DOMException && err.name === "AbortError") {
          reject(new Error("Request to /query/stream timed out after 170000ms"));
          return;
        }
        reject(err);
      }
    })();
  });
}

export function getDemoContrast(): Promise<DemoContrast> {
  return getJson<DemoContrast>("/demo-contrast", 10000, 2);
}

export function getConditions(): Promise<Condition[]> {
  return getJson<Condition[]>("/conditions");
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
