// frontend/src/components/brain-viewer.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { API_BASE_URL, getAtlasQueryUrl, getAtlasUrl, getConditions, getDefaultAtlasUrl, type Condition } from "@/lib/api";
import { buildAnchors, type Anchor, type AnchorId } from "@/lib/brain-anchors";
import { BrainCanvas } from "@/components/brain-canvas";
import { SectionGlow } from "@/components/section-glow";
import { NeuronCanvas } from "@/components/neuron-canvas";

type Props = {
  citedConditionNames?: string[];
};

export function BrainViewer({ citedConditionNames = [] }: Props) {
  const [conditions, setConditions] = useState<Condition[]>([]);
  const [hoverId, setHoverId] = useState<AnchorId | null>(null);
  const [selectedId, setSelectedId] = useState<AnchorId | null>(null);
  const [pressedAnchorId, setPressedAnchorId] = useState<AnchorId | null>(null);
  const [hasError, setHasError] = useState(false);
  const [isAtlasLoaded, setIsAtlasLoaded] = useState(false);
  const [isAtlasSwapping, setIsAtlasSwapping] = useState(false);
  const [view, setView] = useState<"trace" | "atlas">("trace");
  const [atlasRequested, setAtlasRequested] = useState(false);

  useEffect(() => {
    getConditions()
      .then(setConditions)
      .catch(() => setHasError(true));
  }, []);

  // The atlas iframe is a cross-origin nilearn/Plotly render; the backend
  // injects a bridge script into it that postMessages hover picks back here,
  // mirroring BrainCanvas's onHover/onSelect callbacks. Plotly's gl3d
  // mesh3d traces never fire plotly_click (a Plotly.js limitation, not
  // something we can patch around), so a resolved hover also locks in as
  // the selection - this is what makes a tap "stick" on touch devices,
  // where there's no persistent hover state after the finger lifts.
  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      if (event.origin !== new URL(API_BASE_URL).origin) return;
      if (event.data?.source !== "neulittrace-atlas") return;
      const anchorId = (event.data.anchorId ?? null) as AnchorId | null;
      setHoverId(anchorId);
      if (anchorId) setSelectedId(anchorId);
    }
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  const anchors = useMemo(() => buildAnchors(conditions), [conditions]);

  const citedConditionSet = useMemo(() => new Set(citedConditionNames), [citedConditionNames]);

  const highlightedAnchorId = useMemo(() => {
    if (citedConditionSet.size === 0) return null;
    const anchor = anchors.find((a) => a.conditions.some((c) => citedConditionSet.has(c.name)));
    return anchor?.id ?? null;
  }, [anchors, citedConditionSet]);

  const activeAnchorId = hoverId ?? selectedId ?? highlightedAnchorId;
  const activeAnchor: Anchor | undefined = anchors.find((a) => a.id === activeAnchorId);

  const activeConditionName = activeAnchor?.conditions[0]?.name ?? null;
  const pressedAnchor = anchors.find((a) => a.id === pressedAnchorId);
  const pressedConditionName = pressedAnchor?.conditions[0]?.name ?? null;
  const atlasSrc =
    pressedConditionName
      ? getAtlasUrl(pressedConditionName)
      : citedConditionSet.size > 0
        ? getAtlasQueryUrl(citedConditionNames)
        : activeConditionName
          ? getAtlasUrl(activeConditionName)
          : getDefaultAtlasUrl();

  // The atlas iframe is a secondary view: only fetched once the user asks
  // for it, then kept mounted so switching back to it doesn't reload.
  function selectView(next: "trace" | "atlas") {
    setView(next);
    if (next === "atlas") setAtlasRequested(true);
  }

  // Later condition switches just swap the iframe src in place; dip its
  // opacity briefly instead of re-running the full canvas takeover. Detected
  // during render (React's documented pattern for reacting to a changed
  // value without an effect) rather than in a useEffect, since setting state
  // synchronously inside an effect body triggers cascading re-renders.
  const [prevAtlasSrc, setPrevAtlasSrc] = useState(atlasSrc);
  if (atlasSrc !== prevAtlasSrc) {
    setPrevAtlasSrc(atlasSrc);
    if (isAtlasLoaded) setIsAtlasSwapping(true);
  }

  function handleAtlasLoad() {
    setIsAtlasLoaded(true);
    setIsAtlasSwapping(false);
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-col items-center max-w-[640px] mx-auto w-full mb-12">
        <p className="eyebrow">Interactive atlas</p>
        <h2 className="font-display text-3xl md:text-4xl text-ink text-center">Rare conditions, traced to their region.</h2>
        <p className="font-body text-mist text-center mt-4">Hover the brain to see what a region represents. Click a condition below to see which generalized region its literature associates it with.</p>
      </div>

      <div className="relative">
        <div
          className="absolute inset-0 z-0 pointer-events-none overflow-hidden rounded-[16px]"
          style={{
            WebkitMaskImage: "linear-gradient(to bottom, black 0%, black 55%, transparent 92%)",
            maskImage: "linear-gradient(to bottom, black 0%, black 55%, transparent 92%)",
          }}
          aria-hidden="true"
        >
          <NeuronCanvas particleCount={60} rootX={0.3} rootY={0.5} className="absolute inset-0 h-full w-full opacity-80" />
        </div>
        <SectionGlow className="relative z-10 grid grid-cols-1 lg:grid-cols-[1.1fr_0.9fr] gap-8 items-stretch">
        <div className="glass-panel relative h-[460px] md:h-[720px] w-full overflow-hidden">
          {hasError && (
            <div className="absolute inset-0 flex items-center justify-center bg-void-2 z-10">
              <p className="font-body text-mist text-sm">Atlas view unavailable right now.</p>
            </div>
          )}
          {!hasError && anchors.length > 0 && (
            <div
              className="absolute inset-0 transition-opacity duration-300"
              style={{ opacity: view === "trace" ? 1 : 0, pointerEvents: view === "trace" ? "auto" : "none" }}
            >
              <BrainCanvas
                anchors={anchors}
                activeAnchorId={activeAnchorId}
                onHover={setHoverId}
                onSelect={(id) => {
                  setSelectedId(id);
                  setPressedAnchorId(id);
                }}
              />
            </div>
          )}
          {!hasError && atlasRequested && (
            <iframe
              src={atlasSrc}
              onLoad={handleAtlasLoad}
              title="Anatomical atlas"
              className="absolute inset-0 h-full w-full border-0 transition-opacity duration-500"
              style={{
                opacity: view === "atlas" ? (isAtlasSwapping ? 0.55 : isAtlasLoaded ? 1 : 0) : 0,
                pointerEvents: view === "atlas" ? "auto" : "none",
              }}
            />
          )}

          {!hasError && (
            <div className="absolute top-3 right-3 z-10 flex gap-1 rounded-full border border-line-bright bg-void-2/60 backdrop-blur-sm p-1">
              <button
                onClick={() => selectView("trace")}
                className={`rounded-full px-3 py-1.5 text-[11px] font-semibold tracking-wide transition-colors ${
                  view === "trace" ? "bg-accent-purple/25 text-ink" : "text-mist hover:text-ink"
                }`}
              >
                3D trace
              </button>
              <button
                onClick={() => selectView("atlas")}
                className={`rounded-full px-3 py-1.5 text-[11px] font-semibold tracking-wide transition-colors ${
                  view === "atlas" ? "bg-accent-purple/25 text-ink" : "text-mist hover:text-ink"
                }`}
              >
                Atlas scan
              </button>
            </div>
          )}

          <div className="pointer-events-none absolute bottom-3 left-3 right-3 flex flex-col items-center gap-0.5 text-center">
            <span className="font-body text-[10px] uppercase tracking-wider text-mist-dim/80">
              {view === "trace" ? "Stylized rendering" : "Harvard-Oxford atlas · nilearn"}
            </span>
            <span className="font-body text-[11px] text-mist-dim">
              {view === "trace"
                ? "Drag to rotate, scroll or pinch to zoom, click a region to see the affected area."
                : isAtlasLoaded
                  ? "Real anatomical render. Hover or tap a region to see its name and associated conditions."
                  : "Loading anatomical render…"}
            </span>
          </div>
        </div>

        <div className="glass-panel flex flex-col p-7 min-h-[360px] md:min-h-[560px]">
          <div className="flex-1">
            {activeAnchor ? (
              <>
                <div className="eyebrow mb-2">{activeAnchor.label}</div>
                <p className="font-body text-sm leading-relaxed text-mist mb-6">{activeAnchor.blurb}</p>
                <div className="flex flex-col">
                  {citedConditionSet.size > 0 && (
                    <>
                      {activeAnchor.conditions
                        .filter((c) => citedConditionSet.has(c.name))
                        .map((c) => (
                          <div key={c.name} className="py-3 border-t border-line first:border-t-0">
                            <div className="flex justify-between items-baseline gap-3 mb-1.5">
                              <span className="font-body text-sm font-semibold text-ink">{c.name}</span>
                              <span className="text-[11px] font-semibold uppercase tracking-wide px-2.5 py-0.5 rounded-full whitespace-nowrap text-accent-purple bg-accent-purple/10">
                                Cited in this answer
                              </span>
                            </div>
                            <p className="font-body text-[13.5px] leading-relaxed text-mist">{c.region_literature}</p>
                          </div>
                        ))}
                      {activeAnchor.conditions.some((c) => !citedConditionSet.has(c.name)) && (
                        <p className="eyebrow mt-4 mb-1">Other conditions in this region</p>
                      )}
                    </>
                  )}
                  {activeAnchor.conditions
                    .filter((c) => citedConditionSet.size === 0 || !citedConditionSet.has(c.name))
                    .map((c) => (
                      <div key={c.name} className="py-3 border-t border-line first:border-t-0">
                        <div className="flex justify-between items-baseline gap-3 mb-1.5">
                          <span className="font-body text-sm font-semibold text-ink">{c.name}</span>
                          <span
                            className={`text-[11px] font-semibold uppercase tracking-wide px-2.5 py-0.5 rounded-full whitespace-nowrap ${
                              c.rarity === "rare" ? "text-rare bg-rare/10" : "text-common bg-common/10"
                            }`}
                          >
                            {c.rarity === "rare" ? "Rare finding" : "Common baseline"}
                          </span>
                        </div>
                        <p className="font-body text-[13.5px] leading-relaxed text-mist">{c.region_literature}</p>
                      </div>
                    ))}
                </div>
              </>
            ) : (
              <>
                <div className="eyebrow mb-2">Atlas overview</div>
                <p className="font-body text-sm leading-relaxed text-paper mb-6">
                  NeuLitTrace maps this corpus&apos;s literature-anchored presentations across cortical, subcortical, and
                  midbrain structures. Hover a region, or a condition below, to inspect its associated case literature.
                </p>
                <div className="flex flex-col">
                  <div className="eyebrow mb-2">Examples</div>
                  {conditions.slice(0, 4).map((c) => (
                    <div key={c.name} className="py-2.5 border-t border-line first:border-t-0">
                      <p className="font-body text-sm text-mist">
                        Try: <span className="font-semibold text-ink">{c.name}</span>
                      </p>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
        </SectionGlow>
      </div>

      <div className="flex flex-wrap gap-2 mt-2">
        {conditions.map((condition) => {
          const anchor = anchors.find((a) => a.conditions.some((c) => c.name === condition.name));
          const isSelected = anchor?.id === selectedId;
          return (
            <button
              key={condition.name}
              onClick={() => anchor && setSelectedId(anchor.id)}
              className={`rounded-full border px-4 py-2.5 min-h-11 text-xs transition-[color,border-color,background-color,backdrop-filter,transform] active:scale-[0.97] ${
                isSelected
                  ? "border-rare text-rare"
                  : "bg-void-2/40 backdrop-blur-sm border-line-bright text-mist hover:border-mist hover:text-ink"
              }`}
            >
              <span className="font-body">{condition.name}</span>
            </button>
          );
        })}
      </div>
      <p className="font-body text-xs text-mist">
        Location reference from literature, not a diagnostic read.
      </p>
    </section>
  );
}
