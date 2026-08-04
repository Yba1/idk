// frontend/src/lib/brain-anchors.ts
import type { Condition } from "@/lib/api";

export type AnchorId =
  | "frontal"
  | "temporal"
  | "parietal"
  | "occipital"
  | "insular"
  | "cingulate"
  | "subcortical"
  | "midbrain";

type AnchorDef = {
  id: AnchorId;
  label: string;
  blurb: string;
  pos: [number, number, number];
  keywords: string[];
};

// Positions and blurbs are a fixed anatomical layout for this app's own
// brain visualization (not from the design mockup, which used a different
// invented 11-region set). Keyword matching runs against the real
// `atlas_label` text from backend/app/corpus/conditions.py, so which
// conditions attach to which anchor is grounded in the actual corpus data,
// not hardcoded per condition.
const ANCHOR_DEFS: AnchorDef[] = [
  {
    id: "frontal",
    label: "Frontal lobe",
    blurb: "Executive function, behavior regulation, expressive language and motor planning.",
    pos: [0, 0.55, 1.55],
    keywords: ["frontal", "precentral"],
  },
  {
    id: "temporal",
    label: "Temporal lobe",
    blurb: "Semantic memory, auditory processing, lexical retrieval.",
    pos: [1.35, -0.25, 0.35],
    keywords: ["temporal"],
  },
  {
    id: "parietal",
    label: "Parietal lobe",
    blurb: "Sensory integration, spatial orientation, praxis.",
    pos: [0, 0.85, -0.55],
    keywords: ["parietal", "postcentral", "angular"],
  },
  {
    id: "occipital",
    label: "Occipital lobe",
    blurb: "Primary and associative visual processing.",
    pos: [0, 0.15, -1.55],
    keywords: ["occipital"],
  },
  {
    id: "insular",
    label: "Insular cortex",
    blurb: "Interoception and salience processing; integrates with limbic and temporal structures.",
    pos: [0.95, -0.05, 0.55],
    keywords: ["insular", "insula"],
  },
  {
    id: "cingulate",
    label: "Cingulate cortex",
    blurb: "Attention allocation and error monitoring; connects frontal and limbic circuits.",
    pos: [0, 0.5, 0.05],
    keywords: ["cingulate"],
  },
  {
    id: "subcortical",
    label: "Basal ganglia / subcortical nuclei",
    blurb: "Motor initiation, dopaminergic modulation, subcortical relay.",
    pos: [0.35, 0.05, 0.15],
    keywords: ["pallidum", "caudate", "putamen", "thalamus", "basal ganglia", "subcortical"],
  },
  {
    id: "midbrain",
    label: "Brainstem / midbrain",
    blurb: "Autonomic regulation, arousal, cranial nerve nuclei.",
    pos: [0, -1.05, -0.25],
    keywords: ["midbrain", "brainstem", "brain-stem", "pons", "medulla"],
  },
];

export type Anchor = {
  id: AnchorId;
  label: string;
  blurb: string;
  pos: [number, number, number];
  conditions: Condition[];
};

function matchAnchorIds(atlasLabel: string): AnchorId[] {
  const lower = atlasLabel.toLowerCase();
  const matches = ANCHOR_DEFS.filter((a) => a.keywords.some((kw) => lower.includes(kw)));
  return matches.length > 0 ? matches.map((a) => a.id) : ["subcortical"];
}

export function buildAnchors(conditions: Condition[]): Anchor[] {
  const anchors: Anchor[] = ANCHOR_DEFS.map((def) => ({
    id: def.id,
    label: def.label,
    blurb: def.blurb,
    pos: def.pos,
    conditions: [],
  }));
  const byId = new Map(anchors.map((a) => [a.id, a]));

  for (const condition of conditions) {
    for (const id of matchAnchorIds(condition.atlas_label)) {
      byId.get(id)!.conditions.push(condition);
    }
  }

  return anchors.filter((a) => a.conditions.length > 0);
}
