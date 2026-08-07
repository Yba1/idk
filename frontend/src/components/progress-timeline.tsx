const STAGES = [
  { key: "hyde_expand", label: "Expand" },
  { key: "retrieval", label: "Retrieve" },
  { key: "relevance_check", label: "Check" },
  { key: "refine_query", label: "Refine" },
  { key: "summarize", label: "Summarize" },
  { key: "citation_check", label: "Verify" },
];

const DETAIL_LABEL: Record<string, string> = {
  hyde_expand: "hyde_expand · expanding to a hypothetical abstract",
  retrieval: "cortex_search · retrieving candidates",
  relevance_check: "relevance_check · scoring the retrieved set",
  refine_query: "refine_query · second pass",
  summarize: "cortex_complete · writing",
  citation_check: "citation_check · verifying claims",
};

export type ProgressStageEvent = {
  stage: string;
  iteration?: number;
};

type Props = {
  stages: ProgressStageEvent[];
};

export function ProgressTimeline({ stages }: Props) {
  const lastEvent = stages[stages.length - 1];
  const activeIndex = lastEvent ? STAGES.findIndex((s) => s.key === lastEvent.stage) : -1;
  const hasIteration2 = stages.some((e) => e.iteration === 2);

  return (
    <div className="border-t border-blue-200 bg-blue-50 px-6 py-[22px] md:px-[26px]">
      <div className="flex items-start">
        {STAGES.map((stage, index) => {
          const isDone = activeIndex >= 0 && index < activeIndex;
          const isActive = index === activeIndex;
          const isLast = index === STAGES.length - 1;

          return (
            <div key={stage.key} className="flex items-start">
              <div className="flex w-[104px] flex-shrink-0 flex-col items-center gap-2 text-center">
                <div
                  className={`flex h-[18px] w-[18px] items-center justify-center rounded-full ${
                    isDone
                      ? "bg-blue-700"
                      : isActive
                        ? "bg-blue-700 motion-safe:animate-pulse"
                        : "border border-blue-300 bg-white"
                  }`}
                >
                  {isDone && (
                    <svg className="h-3 w-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
                <p className="font-body text-[10.5px] text-ink">
                  {stage.label}
                  {stage.key === "refine_query" && hasIteration2 && (
                    <span className="ml-1 rounded-[2px] bg-warn-bg px-1 py-0.5 font-data text-[9px] text-warn">
                      retry
                    </span>
                  )}
                </p>
              </div>
              {!isLast && (
                <div className={`mt-[9px] h-px w-4 flex-shrink-0 ${isDone ? "bg-blue-700" : "bg-blue-300"}`} />
              )}
            </div>
          );
        })}
      </div>
      {lastEvent && (
        <p className="mt-4 font-data text-xs text-blue-700">{DETAIL_LABEL[lastEvent.stage] ?? lastEvent.stage}</p>
      )}
    </div>
  );
}
