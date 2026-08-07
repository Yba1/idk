// frontend/src/components/brain-viewer.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { API_BASE_URL, getAtlasQueryUrl, getAtlasUrl, getConditions, getDefaultAtlasUrl, type Condition } from "@/lib/api";
import { buildAnchors, type Anchor, type AnchorId } from "@/lib/brain-anchors";
import { BrainCanvas } from "@/components/brain-canvas";
import { SectionRail } from "@/components/section-rail";
import { RarityComparison } from "@/components/rarity-comparison";

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
  const [view, setView] = useState<"trace" | "atlas">("atlas");
  const [atlasRequested, setAtlasRequested] = useState(true);

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
    <section className="bg-blue-50 px-6 py-[110px] md:px-16">
      <div className="mb-10 flex flex-col justify-between gap-6 md:flex-row md:items-end">
        <div>
          <SectionRail number="§02" eyebrow="Anatomical atlas" />
          <h2 className="mt-5 font-display text-[clamp(28px,4vw,44px)] font-medium text-ink">
            Rare conditions, traced to their region.
          </h2>
        </div>
        <p className="max-w-[400px] font-body text-sm text-trace-muted">
          Harvard-Oxford surface atlas, rendered by nilearn from the backend. Hover a region to read what
          the corpus associates with it.
        </p>
      </div>

      <div className="grid grid-cols-1 items-stretch gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="relative border border-rule bg-white shadow-[var(--shadow-glow)]">
          <div className="flex items-center justify-between border-b border-rule px-[18px] py-3.5">
            <span className="font-data text-[11px] text-dim">Harvard-Oxford · nilearn</span>
            <div className="flex gap-[3px] border border-rule p-[3px]">
              <button
                type="button"
                onClick={() => selectView("atlas")}
                className={`px-2.5 py-1 font-body text-xs ${
                  view === "atlas" ? "bg-blue-100 text-blue-800" : "text-dim"
                }`}
              >
                Atlas scan
              </button>
              <button
                type="button"
                onClick={() => selectView("trace")}
                className={`px-2.5 py-1 font-body text-xs ${
                  view === "trace" ? "bg-blue-100 text-blue-800" : "text-dim"
                }`}
              >
                3D trace
              </button>
            </div>
          </div>

          <div
            className="relative h-[460px] overflow-hidden md:h-[520px]"
            style={{ background: "radial-gradient(ellipse at 50% 45%, var(--blue-50) 0%, #fff 68%)" }}
          >
            {hasError && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-white">
                <p className="font-body text-sm text-dim">Atlas view unavailable right now.</p>
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

            <div className="pointer-events-none absolute bottom-[18px] left-[18px] flex gap-2">
              <LegendChip label="Cited region" tone="cited" />
              <LegendChip label="Related region" tone="related" />
              <LegendChip label="No corpus data" tone="none" />
            </div>
          </div>

          <div className="border-t border-rule px-[18px] py-3">
            <p className="font-body text-xs text-dim">Location reference from literature, not a diagnostic read.</p>
          </div>
        </div>

        <div className="border border-rule bg-white p-[26px]">
          {activeAnchor ? (
            <>
              <p className="eyebrow">{activeAnchor.label}</p>
              <p className="mt-2 font-body text-[13.5px] leading-relaxed text-trace-muted">{activeAnchor.blurb}</p>
              <div className="mt-6">
                {activeAnchor.conditions.map((c) => {
                  const isCited = citedConditionSet.has(c.name);
                  const tag = isCited ? "Cited" : c.rarity === "rare" ? "Rare" : "Common";
                  return (
                    <div key={c.name} className="border-t border-blue-200 py-3 first:border-t-0">
                      <div className="mb-1.5 flex items-baseline justify-between gap-3">
                        <span className="font-body text-sm font-semibold text-ink">{c.name}</span>
                        <span
                          className={`whitespace-nowrap rounded-[2px] px-1.5 py-0.5 font-data text-[10px] ${
                            isCited || c.rarity === "rare"
                              ? "border border-blue-200 bg-blue-100 text-blue-800"
                              : "border border-rule bg-white text-dim"
                          }`}
                        >
                          {tag}
                        </span>
                      </div>
                      <p className="font-body text-[13px] text-trace-muted">{c.region_literature}</p>
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <>
              <p className="eyebrow">Atlas overview</p>
              <p className="mt-2 font-body text-[13.5px] leading-relaxed text-trace-muted">
                Trace maps this corpus&apos;s literature-anchored presentations across cortical, subcortical, and
                midbrain structures. Hover a region, or a condition below, to inspect its associated case literature.
              </p>
              <div className="mt-6">
                <p className="eyebrow mb-2">Examples</p>
                {conditions.slice(0, 4).map((c) => (
                  <div key={c.name} className="border-t border-blue-200 py-2.5 first:border-t-0">
                    <p className="font-body text-sm text-trace-muted">
                      Try: <span className="font-semibold text-ink">{c.name}</span>
                    </p>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="mt-6">
        <RarityComparison />
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        {conditions.map((condition) => {
          const anchor = anchors.find((a) => a.conditions.some((c) => c.name === condition.name));
          const isSelected = anchor?.id === selectedId;
          return (
            <button
              key={condition.name}
              type="button"
              onClick={() => anchor && setSelectedId(anchor.id)}
              className={`rounded-[2px] border px-3 py-1.5 font-body text-xs transition-colors ${
                isSelected
                  ? "border-blue-700 text-blue-700"
                  : "border-rule bg-white text-dim hover:border-blue-300 hover:text-ink"
              }`}
            >
              {condition.name}
            </button>
          );
        })}
      </div>
    </section>
  );
}

function LegendChip({ label, tone }: { label: string; tone: "cited" | "related" | "none" }) {
  const dot =
    tone === "cited" ? "bg-blue-600" : tone === "related" ? "bg-blue-400" : "border border-rule bg-white";
  const chipClass =
    tone === "cited"
      ? "border-blue-200 bg-blue-100 text-blue-800"
      : "border-rule bg-white text-dim";
  return (
    <span className={`flex items-center gap-1.5 rounded-[2px] border px-2 py-1 font-data text-[10.5px] ${chipClass}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
}
