// frontend/src/components/brain-canvas.tsx
"use client";

import { useEffect, useRef } from "react";
import type { Anchor, AnchorId } from "@/lib/brain-anchors";

type Props = {
  anchors: Anchor[];
  activeAnchorId: AnchorId | null;
  onHover: (id: AnchorId | null) => void;
  onSelect: (id: AnchorId) => void;
};

type Point = { x: number; y: number; z: number; anchorId: AnchorId; shade: number };
type Projected = { x: number; y: number; z: number; persp: number };

// Anatomical anchor positions in the same local unit-sphere space the point
// cloud is built in (x lateral, y vertical, z anterior/posterior). Adapted
// from docs/design-references/hero-redesign-preview-2026-07-23.html's brain
// canvas, collapsed to this app's 8 anchor ids (no left/right split, no
// cerebellum anchor since no corpus condition maps there).
const ANCHOR_POS: Record<AnchorId, [number, number, number]> = {
  frontal: [0, 0.08, 0.66],
  parietal: [0, 0.5, -0.08],
  occipital: [0, 0.12, -0.66],
  temporal: [0.56, -0.34, 0.16],
  insular: [0.34, -0.02, 0.12],
  cingulate: [0, 0.22, 0.18],
  subcortical: [0, -0.1, -0.02],
  midbrain: [0, -0.5, -0.18],
};

function nearestAnchorId(x: number, y: number, z: number): AnchorId {
  let best = Infinity;
  let id: AnchorId = "frontal";
  (Object.keys(ANCHOR_POS) as AnchorId[]).forEach((a) => {
    const [ax, ay, az] = ANCHOR_POS[a];
    const dd = (x - ax) ** 2 + (y - ay) ** 2 + (z - az) ** 2;
    if (dd < best) {
      best = dd;
      id = a;
    }
  });
  return id;
}

function buildPoints(): Point[] {
  const points: Point[] = [];

  function hemisphere(sign: number) {
    const cx = sign * 0.24;
    const rx = 0.4;
    const ry = 0.58;
    const rz = 0.7;
    for (let i = 0; i < 3400; i++) {
      const u = Math.random();
      const v = Math.random();
      const theta = 2 * Math.PI * u;
      const phi = Math.acos(2 * v - 1);
      const sx = Math.sin(phi) * Math.cos(theta);
      const sy = Math.cos(phi);
      const sz = Math.sin(phi) * Math.sin(theta);

      let taper = 1;
      if (sz > 0.2) taper -= 0.3 * (sz - 0.2);
      if (sz < -0.4) taper -= 0.22 * (-sz - 0.4);
      const flatten = sy < -0.5 ? 0.68 : 1;
      // Slight medial flattening so a longitudinal fissure is visible from
      // above without splitting the hemispheres into two separate blobs.
      const medial = 1 - 0.08 * Math.max(0, 1 - Math.abs(sx));

      const gyri =
        1 +
        0.055 * Math.sin(13 * theta + 6 * phi) +
        0.04 * Math.sin(27 * theta - 10 * phi) +
        0.025 * Math.sin(47 * theta + 19 * phi) +
        (Math.random() - 0.5) * 0.015;
      // Normalized ~[0,1] crest/groove value for gyrus (bright) vs sulcus
      // (dark) shading, independent of the small random jitter above.
      const gyriNorm =
        0.5 +
        0.5 *
          (0.6 * Math.sin(13 * theta + 6 * phi) +
            0.3 * Math.sin(27 * theta - 10 * phi) +
            0.1 * Math.sin(47 * theta + 19 * phi));

      const x = cx + sign * Math.max(Math.abs(sx * rx * taper * medial * gyri), 0.05);
      const y = sy * ry * flatten * gyri + 0.04;
      const z = sz * rz * taper * gyri;
      points.push({ x, y, z, anchorId: nearestAnchorId(x, y, z), shade: gyriNorm });
    }
  }
  hemisphere(-1);
  hemisphere(1);

  function temporalLobe(sign: number) {
    const cx = sign * 0.5;
    const cy = -0.3;
    const cz = 0.14;
    for (let i = 0; i < 650; i++) {
      const u = Math.random();
      const v = Math.random();
      const theta = 2 * Math.PI * u;
      const phi = Math.acos(2 * v - 1);
      const noise = 1 + (Math.random() - 0.5) * 0.06;
      const gyriNorm = 0.55 + 0.45 * Math.sin(15 * theta + 4 * phi);
      const x = cx + Math.sin(phi) * Math.cos(theta) * 0.21 * noise;
      const y = cy + Math.cos(phi) * 0.16 * noise;
      const z = cz + Math.sin(phi) * Math.sin(theta) * 0.42 * noise;
      points.push({ x, y, z, anchorId: "temporal", shade: gyriNorm });
    }
  }
  temporalLobe(-1);
  temporalLobe(1);

  // Cerebellum: a tighter, finer-bumped cluster tucked under the occipital
  // lobes, purely for silhouette recognition (no dedicated anchor exists,
  // so it inherits whichever anchor is nearest, usually occipital/midbrain).
  function cerebellum(sign: number) {
    const cx = sign * 0.16;
    const cy = -0.52;
    const cz = -0.42;
    for (let i = 0; i < 480; i++) {
      const u = Math.random();
      const v = Math.random();
      const theta = 2 * Math.PI * u;
      const phi = Math.acos(2 * v - 1);
      const ridges = 1 + 0.06 * Math.sin(29 * theta + 13 * phi);
      const gyriNorm = 0.55 + 0.45 * Math.sin(29 * theta + 13 * phi);
      const x = cx + Math.sin(phi) * Math.cos(theta) * 0.24 * ridges;
      const y = cy + Math.cos(phi) * 0.16 * ridges;
      const z = cz + Math.sin(phi) * Math.sin(theta) * 0.2 * ridges;
      points.push({ x, y, z, anchorId: nearestAnchorId(x, y, z), shade: gyriNorm });
    }
  }
  cerebellum(-1);
  cerebellum(1);

  for (let i = 0; i < 90; i++) {
    const t = i / 90;
    const wobble = (Math.random() - 0.5) * 0.025;
    points.push({
      x: wobble,
      y: -0.5 - t * 0.42,
      z: -0.2 + t * 0.14 + wobble,
      anchorId: "midbrain",
      shade: 0.7,
    });
  }

  return points;
}

function buildConnectome(points: Point[]): [number, number][] {
  const connectome: [number, number][] = [];
  const pool: number[] = [];
  for (let i = 0; i < points.length; i++) {
    if (points[i].anchorId !== "midbrain") pool.push(i);
  }
  let attempts = 0;
  while (connectome.length < 220 && attempts < 10000) {
    attempts++;
    const a = pool[(Math.random() * pool.length) | 0];
    const b = pool[(Math.random() * pool.length) | 0];
    if (a === b) continue;
    const pa = points[a];
    const pb = points[b];
    const d = Math.sqrt((pa.x - pb.x) ** 2 + (pa.y - pb.y) ** 2 + (pa.z - pb.z) ** 2);
    if (d > 0.14 && d < 0.5) connectome.push([a, b]);
  }
  return connectome;
}

export function BrainCanvas({ anchors, activeAnchorId, onHover, onSelect }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const activeIdRef = useRef(activeAnchorId);
  const onHoverRef = useRef(onHover);
  const onSelectRef = useRef(onSelect);
  const anchorMetaRef = useRef(new Map(anchors.map((a) => [a.id, a])));

  activeIdRef.current = activeAnchorId;
  onHoverRef.current = onHover;
  onSelectRef.current = onSelect;
  anchorMetaRef.current = new Map(anchors.map((a) => [a.id, a]));

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let rotY = 0.5;
    let rotX = 0.34;
    const autoRotate = 0.0015;
    let zoom = 1;
    const MIN_ZOOM = 0.6;
    const MAX_ZOOM = 2.8;
    let dragging = false;
    let dragMoved = false;
    let lastX = 0;
    let lastY = 0;
    let mouseX = 0;
    let mouseY = 0;
    let mouseInside = false;
    let hoverId: AnchorId | null = null;
    const activePointers = new Map<number, { x: number; y: number }>();
    let pinchStartDist = 0;
    let pinchStartZoom = 1;

    const points = buildPoints();
    const connectome = buildConnectome(points);

    let W = 0;
    let H = 0;
    let DPR = 1;
    const resize = () => {
      const rect = canvas.parentElement?.getBoundingClientRect();
      if (!rect) return;
      DPR = window.devicePixelRatio || 1;
      W = rect.width;
      H = rect.height;
      canvas.width = W * DPR;
      canvas.height = H * DPR;
      canvas.style.width = `${W}px`;
      canvas.style.height = `${H}px`;
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    function project(p: { x: number; y: number; z: number }): Projected {
      const cy = Math.cos(rotY);
      const sy = Math.sin(rotY);
      const cx = Math.cos(rotX);
      const sx = Math.sin(rotX);
      const x1 = p.x * cy - p.z * sy;
      const z1 = p.x * sy + p.z * cy;
      const y1 = p.y * cx - z1 * sx;
      const z2 = p.y * sx + z1 * cx;
      const scale = Math.min(W, H) * 1.15 * zoom;
      const persp = 1 / (2.5 - z2);
      return { x: W / 2 + x1 * scale * persp, y: H / 2 - y1 * scale * persp - H * 0.02, z: z2, persp };
    }

    function pinchDistance() {
      const pts = Array.from(activePointers.values());
      if (pts.length < 2) return 0;
      return Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
    }

    const onPointerDown = (e: PointerEvent) => {
      activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      canvas.setPointerCapture(e.pointerId);
      if (activePointers.size === 2) {
        dragging = false;
        pinchStartDist = pinchDistance();
        pinchStartZoom = zoom;
      } else {
        dragging = true;
        dragMoved = false;
        lastX = e.clientX;
        lastY = e.clientY;
      }
    };
    const onPointerMove = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseX = e.clientX - rect.left;
      mouseY = e.clientY - rect.top;
      mouseInside = true;

      if (activePointers.has(e.pointerId)) {
        activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      }

      if (activePointers.size === 2) {
        const dist = pinchDistance();
        if (pinchStartDist > 0 && dist > 0) {
          const next = pinchStartZoom * (dist / pinchStartDist);
          zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, next));
        }
        return;
      }

      if (dragging) {
        const dx = e.clientX - lastX;
        const dy = e.clientY - lastY;
        if (Math.abs(dx) > 2 || Math.abs(dy) > 2) dragMoved = true;
        rotY += dx * 0.006;
        rotX = Math.max(-1.55, Math.min(1.55, rotX - dy * 0.006));
        lastX = e.clientX;
        lastY = e.clientY;
      }
    };
    const onPointerLeave = () => {
      mouseInside = false;
      if (hoverId !== null) {
        hoverId = null;
        onHoverRef.current(null);
      }
    };
    const endPointer = (e: PointerEvent) => {
      activePointers.delete(e.pointerId);
      if (activePointers.size < 2) pinchStartDist = 0;
      if (activePointers.size === 0) {
        dragging = false;
      }
    };
    const onPointerUp = (e: PointerEvent) => {
      const wasSingleDrag = dragging && activePointers.size <= 1;
      endPointer(e);
      if (wasSingleDrag && !dragMoved) {
        const rect = canvas.getBoundingClientRect();
        mouseX = e.clientX - rect.left;
        mouseY = e.clientY - rect.top;
        const region = nearestPointRegion();
        if (region) onSelectRef.current(region);
      }
    };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const next = zoom * (1 - e.deltaY * 0.0012);
      zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, next));
    };

    canvas.addEventListener("pointerdown", onPointerDown);
    canvas.addEventListener("pointermove", onPointerMove);
    canvas.addEventListener("pointerleave", onPointerLeave);
    canvas.addEventListener("pointercancel", endPointer);
    canvas.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("pointerup", onPointerUp);

    function nearestPointRegion(): AnchorId | null {
      if (!mouseInside) return null;
      let bestD = 42 * 42;
      let best: AnchorId | null = null;
      for (let i = 0; i < points.length; i += 2) {
        const proj = project(points[i]);
        if (proj.persp < 0.3) continue;
        const dx = proj.x - mouseX;
        const dy = proj.y - mouseY;
        const dd = dx * dx + dy * dy;
        if (dd < bestD) {
          bestD = dd;
          best = points[i].anchorId;
        }
      }
      return best;
    }

    function updateHover() {
      if (!mouseInside || dragging) {
        if (dragging && hoverId !== null) {
          hoverId = null;
          onHoverRef.current(null);
        }
        return;
      }
      const region = nearestPointRegion();
      if (region !== hoverId) {
        hoverId = region;
        onHoverRef.current(region);
      }
      if (canvas) canvas.style.cursor = region ? "pointer" : "grab";
    }

    let raf = 0;
    let frame = 0;
    function draw() {
      ctx!.clearRect(0, 0, W, H);
      if (!dragging && !reduced) rotY += autoRotate;
      updateHover();
      frame++;

      const activeId = activeIdRef.current;
      const activeMeta = activeId ? anchorMetaRef.current.get(activeId) : undefined;
      const activeIsRare = activeMeta?.conditions.some((c) => c.rarity === "rare") ?? true;
      const activeColor = activeIsRare ? "255,95,163" : "111,168,255";

      // Faint volumetric haze rather than a solid fill, so the point cloud
      // itself (not an opaque backdrop) carries the brain's translucent mass.
      ctx!.globalCompositeOperation = "source-over";
      let minPX = Infinity;
      let maxPX = -Infinity;
      let minPY = Infinity;
      let maxPY = -Infinity;
      for (let i = 0; i < points.length; i += 5) {
        const proj = project(points[i]);
        if (proj.persp < 0.25) continue;
        if (proj.x < minPX) minPX = proj.x;
        if (proj.x > maxPX) maxPX = proj.x;
        if (proj.y < minPY) minPY = proj.y;
        if (proj.y > maxPY) maxPY = proj.y;
      }
      let gcx = W / 2;
      let gcy = H / 2;
      let grOuter = Math.min(W, H) * 0.4;
      if (Number.isFinite(minPX)) {
        gcx = (minPX + maxPX) / 2;
        gcy = (minPY + maxPY) / 2;
        const grx = Math.max(10, (maxPX - minPX) / 2) * 1.02;
        const gry = Math.max(10, (maxPY - minPY) / 2) * 1.05;
        grOuter = gry;
        ctx!.save();
        ctx!.translate(gcx, gcy);
        ctx!.scale(grx / gry, 1);
        const grad = ctx!.createRadialGradient(0, 0, 0, 0, 0, gry);
        grad.addColorStop(0, "rgba(150,120,205,0.08)");
        grad.addColorStop(0.7, "rgba(120,95,180,0.04)");
        grad.addColorStop(1, "rgba(90,70,150,0)");
        ctx!.fillStyle = grad;
        ctx!.beginPath();
        ctx!.arc(0, 0, gry, 0, Math.PI * 2);
        ctx!.fill();
        ctx!.restore();
      }

      ctx!.globalCompositeOperation = "lighter";

      // Kept faint by default so the shaded point surface reads as the brain's
      // shape; only lights up as a network accent on the hovered/active region.
      ctx!.lineWidth = 0.8;
      const activeEdges: number[] = [];
      for (let ci = 0; ci < connectome.length; ci++) {
        const pA = points[connectome[ci][0]];
        const pB = points[connectome[ci][1]];
        const ca = project(pA);
        const cb = project(pB);
        const touchesActive = activeId && (pA.anchorId === activeId || pB.anchorId === activeId);
        const cop = (touchesActive ? 0.7 : 0.05) * ((ca.persp + cb.persp) / 2);
        ctx!.strokeStyle = touchesActive ? `rgba(${activeColor},${cop})` : `rgba(180,140,255,${cop})`;
        ctx!.beginPath();
        ctx!.moveTo(ca.x, ca.y);
        ctx!.lineTo(cb.x, cb.y);
        ctx!.stroke();
        if (touchesActive) activeEdges.push(ci);
      }

      // Traveling pulses along the active region's connectome, tracing a
      // signal through the network instead of a static highlight.
      for (let ei = 0; ei < activeEdges.length; ei++) {
        const [ia, ib] = connectome[activeEdges[ei]];
        const ca = project(points[ia]);
        const cb = project(points[ib]);
        const t = ((frame * 0.012 + ei * 0.37) % 1 + 1) % 1;
        const px = ca.x + (cb.x - ca.x) * t;
        const py = ca.y + (cb.y - ca.y) * t;
        const persp = ca.persp + (cb.persp - ca.persp) * t;
        ctx!.fillStyle = `rgba(${activeColor},${0.9 * persp})`;
        ctx!.beginPath();
        ctx!.arc(px, py, 1.8 * persp, 0, Math.PI * 2);
        ctx!.fill();
      }

      for (let i = 0; i < points.length; i++) {
        const pt = points[i];
        const proj = project(pt);
        const isActive = activeId !== null && pt.anchorId === activeId;
        const dimmed = activeId !== null && !isActive;
        // Rim boost: points near the silhouette's edge in screen space read
        // brighter, like light grazing the surface of a glass shell, so the
        // interior connectome shows through the body of the cloud.
        const edgeDist = Math.min(1, Math.hypot(proj.x - gcx, proj.y - gcy) / grOuter);
        const rim = 0.35 * edgeDist * edgeDist;
        // Gyral crests (shade near 1) render bright and dense; sulcal
        // grooves (shade near 0) stay dim, giving the surface real texture.
        const baseOp =
          (isActive ? 1 : dimmed ? 0.18 : 0.2 + 0.35 * pt.shade + rim) *
          Math.max(0.2, proj.persp - 0.22);
        const radius = (isActive ? 2.4 : 1.1 + 0.8 * pt.shade) * proj.persp;
        const color = isActive ? activeColor : "225,215,240";
        ctx!.fillStyle = `rgba(${color},${baseOp})`;
        ctx!.beginPath();
        ctx!.arc(proj.x, proj.y, radius, 0, Math.PI * 2);
        ctx!.fill();
      }

      ctx!.globalCompositeOperation = "source-over";
      raf = requestAnimationFrame(draw);
    }
    raf = requestAnimationFrame(draw);

    return () => {
      window.removeEventListener("resize", resize);
      canvas.removeEventListener("pointerdown", onPointerDown);
      canvas.removeEventListener("pointermove", onPointerMove);
      canvas.removeEventListener("pointerleave", onPointerLeave);
      canvas.removeEventListener("pointercancel", endPointer);
      canvas.removeEventListener("wheel", onWheel);
      window.removeEventListener("pointerup", onPointerUp);
      cancelAnimationFrame(raf);
    };
    // Point cloud/links/connectome are generated once per mount; hover/select/active
    // state flows through refs read inside the draw loop so this doesn't rebuild
    // the geometry on every prop change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <canvas ref={canvasRef} className="h-full w-full cursor-grab touch-none" />;
}
