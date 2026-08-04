// frontend/src/components/retrieval-trace.tsx
import type { TraceEntry } from "@/lib/api";

export function RetrievalTrace({ trace }: { trace: TraceEntry[] }) {
  if (trace.length === 0) return null;

  return (
    <div
      className="grid gap-5"
      style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}
    >
      {trace.map((entry, index) => (
        <div
          key={entry.iteration}
          style={{ animationDelay: `${index * 200}ms` }}
          className={`glass-panel p-5 flex flex-col gap-3 opacity-100 [animation-fill-mode:backwards] motion-safe:animate-[trace-reveal_400ms_ease-out] border-l-4 ${
            entry.relevant ? "border-l-rare" : "border-l-accent-pink"
          }`}
        >
          <div
            className="w-9 h-9 rounded-full flex items-center justify-center font-bold text-sm text-white"
            style={{ background: 'linear-gradient(135deg, var(--accent-purple), var(--accent-pink))' }}
          >
            {index + 1}
          </div>
          <p className="font-body text-ink text-sm font-bold">{entry.note}</p>
          <div className="flex flex-col gap-1">
            <span className="font-body text-xs text-mist">Iteration <span className="font-bold">{entry.iteration}</span></span>
            <span className="font-body text-xs text-mist">confidence <span className="font-bold">{entry.confidence.toFixed(2)}</span></span>
          </div>
        </div>
      ))}
    </div>
  );
}
