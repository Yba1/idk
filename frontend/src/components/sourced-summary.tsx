import type { QueryResult, ScoredPaper } from "@/lib/api";
import { RarityComparison } from "@/components/rarity-comparison";
import { RetrievalTrace } from "@/components/retrieval-trace";
import { SectionGlow } from "@/components/section-glow";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

function SummaryText({ text }: { text: string }) {
  return text.split(/(\[\d+\])/g).map((part, index) => {
    const citation = part.match(/^\[(\d+)\]$/);
    return citation ? (
      <sup key={`${part}-${index}`}>
        <a className="font-body text-xs font-bold text-rare hover:underline" href={`#citation-${citation[1]}`}>
          {part}
        </a>
      </sup>
    ) : (
      <span key={index}>{part.replaceAll("**", "")}</span>
    );
  });
}

function MemoryMarker({ paper }: { paper: ScoredPaper }) {
  if (paper.memoryMultiplier < 1) {
    return <span className="rounded-full bg-common/10 px-2 py-1 text-[11px] text-common">Seen before</span>;
  }
  if (paper.memoryMultiplier > 1) {
    return (
      <span className="rounded-full bg-rare/10 px-2 py-1 text-[11px] text-rare">
        Builds on your work in {paper.paper.condition}
      </span>
    );
  }
  return null;
}

function CostDetails({ result }: { result: QueryResult }) {
  return (
    <details className="mt-8 border-t border-line pt-5 font-body text-sm">
      <summary className="cursor-pointer text-mist hover:text-ink">
        This answer cost ${result.cost.cost_usd.toFixed(5)} · {result.cost.total_tokens.toLocaleString()} tokens
      </summary>
      <div className="mt-4 grid gap-2">
        {Object.entries(result.cost.by_call_site).map(([site, cost]) => (
          <div key={site} className="flex justify-between gap-4 text-mist">
            <span>{site.replaceAll("_", " ")}</span>
            <span className="font-data text-ink">{cost.tokens.toLocaleString()} · ${cost.cost_usd.toFixed(5)}</span>
          </div>
        ))}
      </div>
    </details>
  );
}

export function SourcedSummary({ result }: { result: QueryResult }) {
  const papersByPmid = new Map(result.papers.map((paper) => [paper.paper.pmid, paper]));

  return (
    <div>
      <div className="mx-auto mb-8 max-w-xl text-center">
        <p className="eyebrow">Sourced summary</p>
        <h2 className="mt-3 font-display text-3xl text-ink md:text-4xl">Citation-backed, not diagnostic.</h2>
        <p className="mt-3 font-body text-sm text-mist">Request {result.request_id}</p>
      </div>

      <SectionGlow>
        <div className="glass-panel p-8">
          {result.memory.seen_filtered > 0 && (
            <p className="mb-5 rounded-xl border border-rare/30 bg-rare/10 p-4 font-body text-sm text-rare">
              {result.memory.seen_filtered}{" "}papers you&apos;ve already read were filtered out.
            </p>
          )}
          {!result.memory.applied && (
            <p className="mb-5 rounded-xl border border-line bg-void-2/40 p-4 font-body text-sm text-mist">
              This answer is unpersonalized because personalization was turned off or memory was unavailable.
            </p>
          )}

          <Tabs defaultValue="summary">
            <TabsList className="mb-6 flex flex-wrap gap-2 bg-transparent p-0">
              {[
                ["summary", "Summary"],
                ["papers", "Papers"],
                ["retrieval", "Retrieval process"],
                ["rarity", "Rarity comparison"],
              ].map(([value, label]) => (
                <TabsTrigger
                  key={value}
                  value={value}
                  className="rounded-full border border-line-bright px-4 py-2 font-body text-sm text-mist transition-all data-[state=active]:border-transparent data-[state=active]:bg-[linear-gradient(135deg,var(--accent-purple),var(--accent-pink))] data-[state=active]:text-white"
                >
                  {label}
                </TabsTrigger>
              ))}
            </TabsList>

            <TabsContent value="summary">
              <div className="font-body text-lg leading-relaxed text-paper [text-wrap:pretty]">
                <SummaryText text={result.summary_markdown} />
              </div>
              {result.citations.length > 0 && (
                <aside className="mt-8 grid gap-3 border-t border-line pt-6">
                  {result.citations.map((citation) => {
                    const paper = papersByPmid.get(citation.pmid);
                    return (
                      <a
                        key={`${citation.index}-${citation.pmid}`}
                        id={`citation-${citation.index}`}
                        href={paper?.paper.url ?? `https://pubmed.ncbi.nlm.nih.gov/${citation.pmid}/`}
                        target="_blank"
                        rel="noreferrer"
                        className="font-body text-sm text-mist hover:text-ink"
                      >
                        <span className="font-bold text-rare">[{citation.index}]</span> {paper?.paper.title ?? `PMID ${citation.pmid}`}
                        {citation.supported === false && <span className="ml-2 text-accent-pink">Not verified</span>}
                      </a>
                    );
                  })}
                </aside>
              )}
              <CostDetails result={result} />
            </TabsContent>

            <TabsContent value="papers">
              <div className="grid gap-4">
                {result.papers.map((paper, index) => (
                  <a
                    key={`${paper.paper.pmid}-${index}`}
                    href={paper.paper.url}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-2xl border border-line p-5 transition-colors hover:border-line-bright"
                  >
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <span className="font-data text-xs text-mist">PMID {paper.paper.pmid}</span>
                      <MemoryMarker paper={paper} />
                    </div>
                    <p className="font-body font-semibold text-ink">{paper.paper.title}</p>
                    <p className="mt-2 font-body text-sm text-mist">{paper.paper.condition}</p>
                  </a>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="retrieval">
              <RetrievalTrace trace={result.trace} />
            </TabsContent>

            <TabsContent value="rarity">
              <RarityComparison />
            </TabsContent>
          </Tabs>
        </div>
      </SectionGlow>
    </div>
  );
}
