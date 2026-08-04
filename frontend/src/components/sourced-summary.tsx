// frontend/src/components/sourced-summary.tsx
import type { QueryResult, FlaggedClaim } from "@/lib/api";
import { SectionGlow } from "@/components/section-glow";
import { RetrievalTrace } from "@/components/retrieval-trace";
import { RarityComparison } from "@/components/rarity-comparison";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

function renderTextWithCitations(text: string, flaggedClaimsMap: Map<string, FlaggedClaim>) {
  const sentencePattern = /(?<=[.!?])\s+/;
  const sentences = text.split(sentencePattern).filter(s => s.trim());

  return sentences.flatMap((sentence, sentenceIdx) => {
    const flaggedClaim = flaggedClaimsMap.get(sentence);
    const isUnflagged = flaggedClaim?.status === "supported";

    const parts = sentence.split(/(\[\d+\])/g);
    const renderedParts = parts.map((part, partIdx) => {
      const match = part.match(/^\[(\d+)\]$/);
      if (match) {
        const number = match[1];
        return (
          <sup key={`${sentenceIdx}-${partIdx}`}>
            <a
              href={`#citation-${number}`}
              id={`citation-marker-${number}`}
              className="text-rare font-body text-xs font-bold no-underline hover:underline"
            >
              {part}
            </a>
          </sup>
        );
      }
      return <span key={`${sentenceIdx}-${partIdx}`}>{part}</span>;
    });

    if (flaggedClaim && !isUnflagged) {
      const statusLabel = flaggedClaim.status === "uncited"
        ? "Uncited"
        : flaggedClaim.status === "invalid_marker"
        ? "Invalid marker"
        : flaggedClaim.status === "unverified"
        ? "Unverified"
        : "Flagged";

      return (
        <span key={`flagged-wrap-${sentenceIdx}`}>
          <span
            className="border-b-2 border-dashed border-accent-pink inline-block"
            title={`${statusLabel}: ${flaggedClaim.reason}`}
          >
            <span className="text-accent-pink mr-1">⚠</span>
            <span>{renderedParts}</span>
          </span>
          {" "}
        </span>
      );
    }

    return (
      <span key={`sentence-${sentenceIdx}`}>
        {renderedParts}
        {" "}
      </span>
    );
  });
}

type Props = {
  result: QueryResult;
  onSuggestedConditionClick?: (conditionName: string) => void;
};

// Rarity weight is this case's share of the corpus's max rarity boost
// (rare cases get a 1.6x retrieval boost, common cases 1.0x baseline —
// see backend/app/retrieval/rarity.py). Rendered as a ring, not a label,
// per the rarity-ring gauge in the source UI design.
const RARE_BOOST = 1.6;
const COMMON_BOOST = 1.0;

function RarityRing({ pct }: { pct: number }) {
  return (
    <div
      className="w-16 h-16 rounded-full flex items-center justify-center"
      style={{ background: `conic-gradient(var(--rare) 0% ${pct}%, oklch(1 0 0 / 0.1) ${pct}% 100%)` }}
    >
      <div
        className="w-12 h-12 rounded-full flex items-center justify-center font-data text-[13px] font-bold text-ink"
        style={{ background: "oklch(0.16 0.03 296)" }}
      >
        {pct}%
      </div>
    </div>
  );
}

function StatHeader({ result }: { result: QueryResult }) {
  const caseContext = result.case_context;
  const lastTrace = result.trace[result.trace.length - 1];
  const regionConfidencePct = lastTrace ? Math.round(lastTrace.confidence * 100) : null;
  const rarityPct = caseContext
    ? Math.round(((caseContext.rarity === "rare" ? RARE_BOOST : COMMON_BOOST) / RARE_BOOST) * 100)
    : null;

  return (
    <div className="grid grid-cols-3 gap-2 border-b border-line-bright pb-6 mb-8">
      <div className="flex flex-col items-center gap-2 text-center">
        {rarityPct !== null ? (
          <RarityRing pct={rarityPct} />
        ) : (
          <span className="font-data text-xl text-ink">N/A</span>
        )}
        <span className="font-body text-xs text-mist">Rarity weight</span>
      </div>
      <div className="flex flex-col items-center justify-center gap-2 border-l border-line-bright pl-2 sm:pl-4">
        <span className="font-data text-3xl font-bold text-ink">{result.citations.length}</span>
        <span className="font-body text-xs text-mist text-center">Sources cited</span>
      </div>
      <div className="flex flex-col items-center justify-center gap-2 border-l border-line-bright pl-2 sm:pl-4">
        <span className="font-data text-xl font-semibold text-rare">
          {regionConfidencePct !== null ? `${regionConfidencePct}%` : "N/A"}
        </span>
        <span className="font-body text-xs text-mist text-center">Region match confidence</span>
      </div>
    </div>
  );
}

function DifferentialSection({ differential }: { differential: QueryResult["differential"] }) {
  if (differential.length === 0) {
    return (
      <p className="font-body text-sm text-mist mt-6 pt-6 border-t border-line">
        No alternate conditions had confident literature support for this query.
      </p>
    );
  }
  return (
    <div className="mt-6 pt-6 border-t border-line">
      <p className="eyebrow mb-3">Differential diagnosis</p>
      <ul className="flex flex-col gap-2 font-body text-sm text-paper">
        {differential.map((item) => {
          const number = item.marker.replace(/[[\]]/g, "");
          return (
            <li key={`${item.condition_name}-${item.marker}`}>
              <a
                href={`#citation-${number}`}
                id={`differential-marker-${number}`}
                className="text-rare no-underline hover:underline"
              >
                {item.condition_name}
              </a>
              <span className="text-mist"> — supported by {item.marker}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function CaseRegionTab({ caseContext }: { caseContext: NonNullable<QueryResult["case_context"]> }) {
  return (
    <div className="flex flex-col gap-5 font-body text-sm">
      <div>
        <p className="eyebrow mb-1">Condition</p>
        <p className="text-ink text-lg">{caseContext.condition_name}</p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <p className="eyebrow mb-1">Rarity</p>
          <p className="text-paper capitalize">{caseContext.rarity}</p>
        </div>
        <div>
          <p className="eyebrow mb-1">Corpus papers</p>
          <p className="text-paper">{caseContext.corpus_paper_count}</p>
        </div>
      </div>
      <div>
        <p className="eyebrow mb-1">Region (literature)</p>
        <p className="text-paper">{caseContext.region_literature}</p>
      </div>
      <div>
        <p className="eyebrow mb-1">Atlas label</p>
        <p className="text-paper">{caseContext.atlas_label}</p>
      </div>
      {caseContext.imaging_findings && (
        <div>
          <p className="eyebrow mb-1">Imaging findings</p>
          <p className="text-paper">{caseContext.imaging_findings}</p>
        </div>
      )}
      {caseContext.teaching_point && (
        <div className="border-l-2 border-rare pl-4">
          <p className="eyebrow mb-1">Teaching point</p>
          <p className="text-paper">{caseContext.teaching_point}</p>
        </div>
      )}
    </div>
  );
}

export function SourcedSummary({ result, onSuggestedConditionClick }: Props) {
  const flaggedClaimsMap = new Map(
    result.flagged_claims
      .filter(claim => claim.status !== "supported")
      .map(claim => [claim.sentence, claim])
  );

  const tabs: { value: string; label: string }[] = [{ value: "summary", label: "Summary" }];
  if (result.case_context) tabs.push({ value: "case", label: "Case & region" });
  tabs.push({ value: "retrieval", label: "Retrieval process" });
  tabs.push({ value: "rarity", label: "Rarity comparison" });

  let eyebrowLabel = "Sourced summary";
  let heading = "Citation-backed, not diagnostic.";
  let subheading = result.citations[0]?.condition
    ? `Generated for the ${result.citations[0].condition} pattern in your search above.`
    : "Generated from your search above.";

  const summaryTabContent = result.degraded ? (
    <div className="border-l-2 border-accent-pink pl-6">
      <p className="font-body text-sm text-accent-pink">
        Summary generation degraded. The Paritok/LLM call did not return a
        result. Retry the query.
      </p>
    </div>
  ) : result.no_match ? (
    <div className="mt-2">
      {result.too_generic && (
        <div className="border-l-2 border-rare pl-4 mb-6 max-w-xl mx-auto">
          <p className="font-body text-sm text-paper mb-2">
            Your query looks close to a condition we cover, but it&apos;s too general for us to
            confidently match literature to it. For the most accurate result, include:
          </p>
          <ul className="font-body text-sm text-mist list-disc list-inside space-y-1 mb-2">
            <li>a scan type (e.g. FDG-PET, DAT-SPECT, MRI)</li>
            <li>a symptom or clinical sign</li>
            <li>a brain region, if you know it</li>
          </ul>
          <p className="font-body text-sm text-mist-dim">
            Example: &ldquo;{result.example_query ?? "asymmetric parietal hypometabolism on FDG-PET with progressive apraxia"}&rdquo;
          </p>
        </div>
      )}
      {result.suggested_conditions.length > 0 && (
        <>
          <p className="font-body text-sm text-mist mb-4 text-center">Suggested conditions:</p>
          <div className="flex flex-wrap gap-3 justify-center">
            {result.suggested_conditions.map((condition) => (
              <button
                key={condition.name}
                onClick={() => onSuggestedConditionClick?.(condition.name)}
                className="px-5 py-2 rounded-full font-body text-sm font-medium transition-all duration-150
                  bg-void-2 border border-line-bright text-ink
                  hover:border-accent-pink hover:bg-void
                  active:scale-95
                  disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <span className="font-body text-xs text-mist-dim mr-2">({condition.paper_count})</span>
                <span>{condition.name}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  ) : (
    <div>
      {result.too_generic && (
        <div className="border-l-2 border-rare pl-4 mb-6">
          <p className="font-body text-sm text-paper mb-2">
            Your query is a bit general. This is our best match, but for a more accurate
            result, try including:
          </p>
          <ul className="font-body text-sm text-mist list-disc list-inside space-y-1 mb-2">
            <li>a scan type (e.g. FDG-PET, DAT-SPECT, MRI)</li>
            <li>a symptom or clinical sign</li>
            <li>a brain region, if you know it</li>
          </ul>
          <p className="font-body text-sm text-mist-dim">
            Example: &ldquo;{result.example_query ?? "asymmetric parietal hypometabolism on FDG-PET with progressive apraxia"}&rdquo;
          </p>
        </div>
      )}
      <div className="font-body text-lg leading-relaxed text-paper [text-wrap:pretty]">
        {renderTextWithCitations(result.summary_text, flaggedClaimsMap)}
      </div>
      <DifferentialSection differential={result.differential} />
    </div>
  );

  if (result.degraded) {
    eyebrowLabel = "Sourced summary";
    heading = "Summary generation degraded";
    subheading = "";
  } else if (result.no_match) {
    if (result.too_generic) {
      eyebrowLabel = "Query too general";
      heading = "Try adding more detail";
      subheading = "";
    } else {
      eyebrowLabel = "No match found";
      heading = "No strong match in our corpus";
      subheading = "We did not find literature strongly matching this query in our 329-paper corpus.";
    }
  }

  const showStatHeader = !result.degraded && !result.no_match;
  const showCitationsRail = !result.degraded && !result.no_match && result.citations.length > 0;

  return (
    <div>
      <div className="mb-8 text-center max-w-xl mx-auto">
        <div className="eyebrow">{eyebrowLabel}</div>
        <h2 className="font-display text-3xl md:text-4xl text-ink mt-3">{heading}</h2>
        {subheading && <p className="font-body text-sm text-mist mt-3">{subheading}</p>}
      </div>

      <SectionGlow>
      <div className="glass-panel p-8">
        {showStatHeader && <StatHeader result={result} />}

        <Tabs defaultValue="summary">
          <TabsList className="mb-6 flex flex-wrap gap-2 bg-transparent p-0">
            {tabs.map((tab) => (
              <TabsTrigger
                key={tab.value}
                value={tab.value}
                className="rounded-full px-4 py-2 font-body text-sm font-medium border border-line-bright text-mist
                  data-[state=active]:text-white data-[state=active]:border-transparent
                  data-[state=active]:bg-[linear-gradient(135deg,var(--accent-purple),var(--accent-pink))]
                  transition-all duration-150"
              >
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>

          <div className={showCitationsRail ? "grid grid-cols-1 gap-8 md:grid-cols-[62ch_1fr]" : ""}>
            <div>
              <TabsContent value="summary">{summaryTabContent}</TabsContent>

              {result.case_context && (
                <TabsContent value="case">
                  <CaseRegionTab caseContext={result.case_context} />
                </TabsContent>
              )}

              <TabsContent value="retrieval">
                <p className="font-body text-sm text-mist mb-4">How this answer was produced.</p>
                <RetrievalTrace trace={result.trace} />
              </TabsContent>

              <TabsContent value="rarity">
                <RarityComparison />
              </TabsContent>
            </div>

            {showCitationsRail && (
              <aside className="flex flex-col gap-4 border-l border-line pl-6">
                {result.citations.map((citation) => {
                  const number = citation.marker.replace(/[[\]]/g, "");
                  return (
                    <div key={citation.marker} id={`citation-${number}`} className="font-body text-sm scroll-mt-4">
                      <a href={`#citation-marker-${number}`} className="text-rare font-bold no-underline hover:underline">
                        {citation.marker}
                      </a>{" "}
                      <span className="text-mist text-xs">PMID {citation.pmid}</span>
                      <p className="text-ink text-[13.5px] leading-snug mt-1">{citation.title}</p>
                    </div>
                  );
                })}
              </aside>
            )}
          </div>
        </Tabs>
      </div>
      </SectionGlow>
    </div>
  );
}
