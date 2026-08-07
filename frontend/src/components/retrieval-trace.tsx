// frontend/src/components/retrieval-trace.tsx
import type { TraceEntry } from "@/lib/api";

export function RetrievalTrace({ trace }: { trace: TraceEntry[] }) {
  if (trace.length === 0) {
    return <p className="p-6 font-body text-sm text-dim">No retrieval rounds recorded.</p>;
  }

  return (
    <div>
      {trace.map((entry) => (
        <div
          key={entry.iteration}
          className="grid items-center gap-5 border-t border-rule py-[18px] first:border-t-0"
          style={{ gridTemplateColumns: "44px minmax(0,1fr) 120px 92px" }}
        >
          <span className="font-data text-xs text-dim">{String(entry.iteration).padStart(2, "0")}</span>
          <div>
            <p className="font-body text-sm font-semibold text-ink">Iteration {entry.iteration}</p>
            <p className="mt-1 font-body text-[12.5px] text-trace-muted">
              {entry.note}
              {entry.memory_applied && " · memory applied"}
              {entry.seen_filtered > 0 && ` · ${entry.seen_filtered} seen filtered`}
            </p>
            <div className="mt-2 flex items-center gap-2">
              <span className="h-1 w-24 overflow-hidden rounded-full bg-blue-200">
                <span
                  className={`block h-full ${entry.relevant ? "bg-blue-600" : "bg-rule"}`}
                  style={{ width: `${Math.round(entry.confidence * 100)}%` }}
                />
              </span>
              <span className="font-data text-[11px] text-dim">Confidence {entry.confidence.toFixed(2)}</span>
            </div>
          </div>
          <span className="font-data text-xs text-dim">{entry.retrieved_pmids.length} retrieved</span>
          <span
            className={`w-fit whitespace-nowrap rounded-[2px] border px-2 py-1 font-data text-[10px] ${
              entry.relevant
                ? "border-blue-200 bg-blue-100 text-blue-800"
                : "border-rule bg-white text-dim"
            }`}
          >
            {entry.relevant ? "PASS" : "LOW CONFIDENCE"}
          </span>
        </div>
      ))}
    </div>
  );
}
