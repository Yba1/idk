// Generates docs/public/diagrams/tech-stack.svg — a packed radial bubble map.
// D2's layout engines (dagre/elk) only produce hierarchical box trees, not a
// packed radial/bubble layout, so this is hand-built instead (same approach
// used for SeniorMove+'s tech-stack-bubblemap.mjs).
//
// Every leaf node here matches this repo's own confirmed stack (see
// docs/architecture.md "Technology stack" section and CLAUDE.md's "Confirmed
// stack and architecture"). Colors reuse the same soft-pastel palette as
// docs/public/diagrams/*.d2 (trigger/logic/external/storage/review) so the
// whole diagram set reads as one system.
//
// Layout: category anchors sit on a fixed ring around the hub. Leaf positions
// start as a rough angular fan around their category, then an iterative
// relaxation pass (see resolveCollisions) pushes any overlapping pair of
// bubbles apart until nothing overlaps.

import { writeFileSync } from "node:fs";

const CATEGORIES = [
  {
    key: "presentation",
    label: "Presentation",
    fill: "#e1d5e7", stroke: "#9673a6", text: "#3d2b4a", // = trigger
    leaves: [
      "Next.js 16.2.11\n(App Router)",
      "React 19.2.4",
      "TypeScript 5",
      "Tailwind CSS 4",
      "shadcn/ui\n(Radix primitives)",
    ],
  },
  {
    key: "api",
    label: "API",
    fill: "#dae8fc", stroke: "#6c8ebf", text: "#1c3a5e", // = logic
    leaves: [
      "FastAPI\n(>=0.115.0)",
      "Pydantic\nvalidation",
      "uvicorn",
      "slowapi\n(rate limiting)",
      "httpx",
    ],
  },
  {
    key: "retrieval",
    label: "Retrieval &\nPipeline",
    fill: "#dae8fc", stroke: "#6c8ebf", text: "#1c3a5e", // = logic
    leaves: [
      "rank-bm25\n(lexical search)",
      "sentence-transformers\n(vector search)",
      "nilearn\n(brain atlas)",
      "matplotlib, plotly",
    ],
  },
  {
    key: "external",
    label: "External\nServices",
    fill: "#d5e8d4", stroke: "#82b366", text: "#2d4a26", // = external
    leaves: [
      "Groq API\n(llama-3.3-70b-versatile)",
      "Paritok proxy\n(127.0.0.1:8080)",
      "Paritok GPU\n(compression)",
      "Gemini API\n(gemini-flash-latest, fallback)",
      "OpenAI SDK 1.40+\n(client shape)",
    ],
  },
  {
    key: "data",
    label: "Data Storage",
    fill: "#f5f5f5", stroke: "#666666", text: "#333333", // = storage
    leaves: [
      "Flat JSON corpus\n(329 papers,\n14 conditions)",
      "In-memory\nat startup",
    ],
  },
  {
    key: "tooling",
    label: "Docs &\nTooling",
    fill: "#fff2cc", stroke: "#d6b656", text: "#5c4a13", // = review
    leaves: [
      "D2 diagrams",
      "VitePress\n(MathJax enabled)",
      "pytest\n(99 tests)",
    ],
  },
];

const HUB_R = 80;
const CAT_R = 250;
const LEAF_R_NEAR = 340;
const LEAF_R_FAR = 440;
const CAT_RX = 98, CAT_RY = 46;
const LEAF_RX = 78, LEAF_RY = 30;
const GAP = 10; // minimum clearance kept between any two bubble edges

const LEGEND_ROWS = CATEGORIES.length;
const LEGEND_X0 = 24, LEGEND_Y0 = 12, LEGEND_W = 260, LEGEND_H = LEGEND_ROWS * 30 + 38;

function polar(cx, cy, r, angleDeg) {
  const a = (angleDeg - 90) * (Math.PI / 180);
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
}

function esc(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function multilineText(x, y, text, fontSize, color, bold = false, lineHeight = fontSize * 1.18) {
  const lines = text.split("\n");
  const startY = y - ((lines.length - 1) * lineHeight) / 2;
  return lines
    .map(
      (line, i) =>
        `<text x="${x}" y="${startY + i * lineHeight}" text-anchor="middle" dominant-baseline="middle" font-family="Inter, 'Segoe UI', sans-serif" font-size="${fontSize}" ${bold ? 'font-weight="700"' : ""} fill="${color}">${esc(line)}</text>`
    )
    .join("");
}

// --- build initial nodes -----------------------------------------------

const CX0 = 800, CY0 = 800; // provisional center; canvas is cropped to fit at the end
const angleStep = 360 / CATEGORIES.length;

const catNodes = [];
const leafNodes = [];

CATEGORIES.forEach((cat, ci) => {
  const catAngle = ci * angleStep;
  const [catX, catY] = polar(CX0, CY0, CAT_R, catAngle);
  catNodes.push({ cat, x: catX, y: catY, rx: CAT_RX, ry: CAT_RY, angle: catAngle, fixed: true });

  const leafCount = cat.leaves.length;
  const spread = angleStep * 0.8;
  const leafStart = catAngle - spread / 2;
  const leafStep = leafCount > 1 ? spread / (leafCount - 1) : 0;

  cat.leaves.forEach((leaf, li) => {
    const leafAngle = leafCount > 1 ? leafStart + li * leafStep : catAngle;
    const r = li % 2 === 0 ? LEAF_R_NEAR : LEAF_R_FAR;
    const [leafX, leafY] = polar(CX0, CY0, r, leafAngle);
    leafNodes.push({
      cat, text: leaf, x: leafX, y: leafY, rx: LEAF_RX, ry: LEAF_RY, catRef: catNodes[ci], fixed: false,
    });
  });
});

// --- collision relaxation -------------------------------------------------
// Pushes overlapping (or too-close) bubble pairs apart along their center
// line, and pushes bubbles out of the legend's rectangle, until nothing
// overlaps or an iteration cap is hit. Fixed nodes (category anchors, hub)
// don't move; only leaves absorb the full push.

const hubNode = { x: CX0, y: CY0, rx: HUB_R, ry: HUB_R, fixed: true };
const allMovable = leafNodes;
const allFixed = [hubNode, ...catNodes];

function ellipseOverlap(a, b, gap) {
  const dx = a.x - b.x, dy = a.y - b.y;
  const dist = Math.sqrt(dx * dx + dy * dy) || 0.0001;
  const rxSum = a.rx + b.rx + gap, rySum = a.ry + b.ry + gap;
  // normalized (elliptical) distance; < 1 means overlapping
  const nx = dx / rxSum, ny = dy / rySum;
  const norm = Math.sqrt(nx * nx + ny * ny) || 0.0001;
  return { dx, dy, dist, norm, overlapping: norm < 1 };
}

for (let iter = 0; iter < 400; iter++) {
  let anyOverlap = false;

  for (let i = 0; i < allMovable.length; i++) {
    for (let j = i + 1; j < allMovable.length; j++) {
      const a = allMovable[i], b = allMovable[j];
      const o = ellipseOverlap(a, b, GAP);
      if (o.overlapping) {
        anyOverlap = true;
        const push = (1 - o.norm) * 0.5 + 0.5;
        const ux = o.dx / o.dist, uy = o.dy / o.dist;
        const moveX = ux * push * 4, moveY = uy * push * 4;
        a.x += moveX; a.y += moveY;
        b.x -= moveX; b.y -= moveY;
      }
    }
    for (const f of allFixed) {
      const o = ellipseOverlap(allMovable[i], f, GAP);
      if (o.overlapping) {
        anyOverlap = true;
        const push = (1 - o.norm) * 0.5 + 0.5;
        const ux = o.dx / o.dist, uy = o.dy / o.dist;
        allMovable[i].x += ux * push * 4;
        allMovable[i].y += uy * push * 4;
      }
    }
    // legend AABB repulsion
    const leaf = allMovable[i];
    const ex1 = leaf.x - leaf.rx, ex2 = leaf.x + leaf.rx;
    const ey1 = leaf.y - leaf.ry, ey2 = leaf.y + leaf.ry;
    const lx1 = LEGEND_X0, lx2 = LEGEND_X0 + LEGEND_W;
    const ly1 = LEGEND_Y0, ly2 = LEGEND_Y0 + LEGEND_H;
    const overlapsLegend = ex1 < lx2 + GAP && ex2 > lx1 - GAP && ey1 < ly2 + GAP && ey2 > ly1 - GAP;
    if (overlapsLegend) {
      anyOverlap = true;
      const distRight = lx2 + GAP - ex1;
      const distBottom = ly2 + GAP - ey1;
      if (distRight < distBottom) leaf.x += 5; else leaf.y += 5;
    }
  }

  if (!anyOverlap) break;
}

// --- render ---------------------------------------------------------------

let shapes = [];
let connectors = [];

catNodes.forEach((cn) => {
  connectors.push(
    `<line x1="${CX0}" y1="${CY0}" x2="${cn.x}" y2="${cn.y}" stroke="${cn.cat.stroke}" stroke-width="2.5" opacity="0.7" />`
  );
});

leafNodes.forEach((leaf) => {
  const cn = leaf.catRef;
  connectors.push(
    `<line x1="${cn.x}" y1="${cn.y}" x2="${leaf.x}" y2="${leaf.y}" stroke="${leaf.cat.stroke}" stroke-width="1.5" opacity="0.5" />`
  );
  shapes.push(
    `<ellipse cx="${leaf.x}" cy="${leaf.y}" rx="${leaf.rx}" ry="${leaf.ry}" fill="${leaf.cat.fill}" stroke="${leaf.cat.stroke}" stroke-width="1.5" />`
  );
  shapes.push(multilineText(leaf.x, leaf.y, leaf.text, 12, leaf.cat.text));
});

catNodes.forEach((cn) => {
  shapes.push(
    `<ellipse cx="${cn.x}" cy="${cn.y}" rx="${cn.rx}" ry="${cn.ry}" fill="${cn.cat.fill}" stroke="${cn.cat.stroke}" stroke-width="2.5" />`
  );
  shapes.push(multilineText(cn.x, cn.y, cn.cat.label, 19.5, cn.cat.text, true));
});

const hub = `
  <circle cx="${CX0}" cy="${CY0}" r="${HUB_R}" fill="#0D32B2" stroke="#0A0F25" stroke-width="2.5" />
  ${multilineText(CX0, CY0, "NeuLitTrace\nStack", 17, "#FFFFFF", true)}
`;

const legend = `
  <g>
    <rect x="${LEGEND_X0}" y="${LEGEND_Y0}" width="${LEGEND_W}" height="${LEGEND_H}" rx="10" fill="#FFFFFF" stroke="#E5E7EB" stroke-width="1.5" />
    <text x="${LEGEND_X0 + 16}" y="${LEGEND_Y0 + 22}" font-family="Inter, 'Segoe UI', sans-serif" font-size="17" font-weight="700" fill="#111827">Layer Key</text>
    ${CATEGORIES.map(
  (cat, i) => `
      <rect x="${LEGEND_X0 + 16}" y="${LEGEND_Y0 + 37 + i * 30}" width="18" height="18" rx="4" fill="${cat.fill}" stroke="${cat.stroke}" stroke-width="1.5" />
      <text x="${LEGEND_X0 + 42}" y="${LEGEND_Y0 + 50 + i * 30}" font-family="Inter, 'Segoe UI', sans-serif" font-size="15" fill="#374151">${esc(cat.label.replace("\n", " "))}</text>
    `
).join("")}
  </g>
`;

// --- crop canvas to the actual content bounds -----------------------------

const PAD_LEFT = 10, PAD_RIGHT = 60, PAD_TOP = 10, PAD_BOTTOM = 60;
const allEllipses = [hubNode, ...catNodes, ...leafNodes];
let minX = LEGEND_X0, maxX = LEGEND_X0 + LEGEND_W, minY = LEGEND_Y0, maxY = LEGEND_Y0 + LEGEND_H;
allEllipses.forEach((e) => {
  minX = Math.min(minX, e.x - e.rx);
  maxX = Math.max(maxX, e.x + e.rx);
  minY = Math.min(minY, e.y - e.ry);
  maxY = Math.max(maxY, e.y + e.ry);
});
minX -= PAD_LEFT; minY -= PAD_TOP; maxX += PAD_RIGHT; maxY += PAD_BOTTOM;
const width = maxX - minX;
const height = maxY - minY;

const svg = `<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="${minX} ${minY} ${width} ${height}" width="${width}" height="${height}">
  <rect x="${minX}" y="${minY}" width="${width}" height="${height}" fill="#FFFFFF" />
  <g>${connectors.join("\n")}</g>
  <g>${shapes.join("\n")}</g>
  ${hub}
  ${legend}
</svg>
`;

writeFileSync(new URL("./tech-stack.svg", import.meta.url), svg);

// --- self-check: verify zero overlaps before declaring success ------------

let remaining = 0;
for (let i = 0; i < allMovable.length; i++) {
  for (let j = i + 1; j < allMovable.length; j++) {
    if (ellipseOverlap(allMovable[i], allMovable[j], 0).overlapping) remaining++;
  }
  for (const f of allFixed) {
    if (ellipseOverlap(allMovable[i], f, 0).overlapping) remaining++;
  }
}
console.log(`wrote tech-stack.svg (${allEllipses.length} bubbles, ${remaining} residual overlaps)`);
