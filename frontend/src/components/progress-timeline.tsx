const STAGES = [
  { key: "hyde_expand", label: "Expanding query" },
  { key: "retrieval", label: "Searching literature" },
  { key: "relevance_check", label: "Checking relevance" },
  { key: "refine_query", label: "Refining search" },
  { key: "compress", label: "Compressing context" },
  { key: "summarize", label: "Writing summary" },
  { key: "citation_check", label: "Verifying citations" },
];

export type ProgressStageEvent = {
  stage: string;
  iteration?: number;
};

type Props = {
  stages: ProgressStageEvent[];
};

const ACCENT_GRADIENT = "linear-gradient(135deg, var(--accent-purple), var(--accent-pink))";

export function ProgressTimeline({ stages }: Props) {
  if (stages.length === 0) return null;

  const lastEvent = stages[stages.length - 1];
  const activeIndex = STAGES.findIndex((s) => s.key === lastEvent.stage);
  const hasIteration2 = stages.some((e) => e.iteration === 2);

  return (
    <div className="w-full overflow-x-auto pb-1">
      <div className="flex items-start min-w-max px-1">
        {STAGES.map((stage, index) => {
          let status: "done" | "active" | "pending";

          if (index < activeIndex) {
            status = "done";
          } else if (index === activeIndex) {
            status = "active";
          } else {
            status = "pending";
          }

          const isDone = status === "done";
          const isActive = status === "active";
          const isLast = index === STAGES.length - 1;

          return (
            <div key={stage.key} className="flex items-start">
              <div className="flex flex-col items-center gap-2 w-24 flex-shrink-0">
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${
                    isActive
                      ? "motion-safe:animate-pulse"
                      : isDone
                        ? ""
                        : "border border-solid"
                  }`}
                  style={
                    isDone || isActive
                      ? { background: ACCENT_GRADIENT }
                      : { borderColor: "var(--text-secondary)" }
                  }
                >
                  {isDone && (
                    <svg
                      className="w-4 h-4 text-white"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                  {isActive && <div className="w-2 h-2 rounded-full bg-white" />}
                </div>

                <div className="flex flex-col items-center gap-1">
                  <p
                    className={`font-body text-xs font-bold text-center leading-tight ${
                      isDone || isActive ? "text-ink" : "text-mist"
                    }`}
                  >
                    {stage.label}
                  </p>
                  {stage.key === "refine_query" && hasIteration2 && (
                    <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold bg-accent-pink text-white">
                      Retry
                    </span>
                  )}
                </div>
              </div>

              {!isLast && (
                <div
                  className={`h-0.5 w-8 mt-[13px] flex-shrink-0 ${isActive ? "motion-safe:animate-pulse" : ""}`}
                  style={{
                    background: isDone ? ACCENT_GRADIENT : "var(--text-secondary)",
                    opacity: isDone ? 1 : isActive ? 0.5 : 0.3,
                  }}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
