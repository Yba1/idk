// frontend/src/components/query-form.tsx
"use client";

import { useState } from "react";
import { queryLiteratureStream, type QueryResult } from "@/lib/api";
import { SectionGlow } from "@/components/section-glow";
import { ProgressTimeline, type ProgressStageEvent } from "@/components/progress-timeline";
import { WakingLoader } from "@/components/waking-loader";

type Props = {
  onResult: (result: QueryResult) => void;
  onCurrentQueryChange?: (query: string) => void;
};

export function QueryForm({ onResult, onCurrentQueryChange }: Props) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [stages, setStages] = useState<ProgressStageEvent[]>([]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    submitQuery(query.trim());
  }

  async function submitQuery(queryText: string) {
    if (!queryText.trim()) return;

    onCurrentQueryChange?.(queryText.trim());
    setStages([]);
    setStatus("loading");
    try {
      const result = await queryLiteratureStream(queryText.trim(), (stage, detail) => {
        setStages((prev) => [...prev, { stage, iteration: detail.iteration }]);
      });
      onResult(result);
      setStatus("idle");
    } catch {
      setStatus("error");
    }
  }

  function handleQueryChange(value: string) {
    setQuery(value);
    onCurrentQueryChange?.(value);
  }

  return (
    <SectionGlow>
      <form onSubmit={handleSubmit} className="glass-panel flex flex-col gap-4 p-7">
        <span className="eyebrow">Describe the finding</span>
        <textarea
          value={query}
          onChange={(event) => handleQueryChange(event.target.value)}
          placeholder="asymmetric parietal hypometabolism on FDG-PET with progressive apraxia"
          rows={3}
          className="font-body text-lg bg-transparent resize-none outline-none placeholder:text-mist"
          disabled={status === "loading"}
        />
        <p className="font-body text-sm text-mist">
          Tip: mention a scan type (like FDG-PET), a symptom, or a brain region for the best match.
        </p>
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={status === "loading" || !query.trim()}
            className="btn-gradient rounded-full px-8 py-3 font-body font-semibold text-white transition-transform active:scale-[0.98] disabled:opacity-40"
          >
            {status === "loading" ? "Searching" : "Search"}
          </button>
        </div>
        {status === "loading" && stages.length === 0 && <WakingLoader />}
        {status === "loading" && stages.length > 0 && <ProgressTimeline stages={stages} />}
        {status === "error" && (
          <p className="font-body text-sm text-accent-pink">
            Retrieval degraded. The backend did not respond. Confirm it is running and try again.
          </p>
        )}
      </form>
    </SectionGlow>
  );
}
