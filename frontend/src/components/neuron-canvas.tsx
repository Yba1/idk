// frontend/src/components/neuron-canvas.tsx
"use client";

import { useEffect, useRef } from "react";

type Particle = {
  x: number;
  y: number;
  r: number;
  vx: number;
  vy: number;
  phase: number;
};

function drawNeuronBranch(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  angle: number,
  length: number,
  depth: number,
  t: number,
  seed: number
) {
  if (depth <= 0 || length < 4) return;
  const sway = Math.sin(t * 0.35 + seed) * 0.1;
  const a = angle + sway;
  const x2 = x + Math.cos(a) * length;
  const y2 = y + Math.sin(a) * length;

  // Brightness band traveling outward through the tree, design-system/MASTER.md section 7.
  const wave = 0.5 + 0.5 * Math.sin(t * 1.15 - depth * 0.9 + seed * 0.4);
  const opacity = Math.min(0.95, 0.44 + depth * 0.1 + wave * 0.18);

  const grad = ctx.createLinearGradient(x, y, x2, y2);
  grad.addColorStop(0, `rgba(78,138,226,${opacity})`);
  grad.addColorStop(1, `rgba(150,190,250,${opacity * 0.62})`);
  ctx.strokeStyle = grad;
  ctx.lineWidth = Math.max(0.7, depth * 0.82);
  ctx.lineCap = "round";

  ctx.beginPath();
  ctx.moveTo(x, y);
  const bend = Math.sin(t * 0.3 + seed * 1.7) * length * 0.12;
  const mx = (x + x2) / 2 + Math.cos(a + Math.PI / 2) * bend;
  const my = (y + y2) / 2 + Math.sin(a + Math.PI / 2) * bend;
  ctx.quadraticCurveTo(mx, my, x2, y2);
  ctx.stroke();
  // A second, wider, low-alpha stroke over the same path stands in for
  // shadowBlur's emission glow - ctx.shadowBlur is one of the most
  // expensive Canvas2D operations (effectively a per-call blur pass) and
  // at up to ~500 branch strokes/frame it was crashing the renderer in
  // this environment's headless/software-rendered Chromium. Two strokes is
  // cheap; shadowBlur on hundreds of paths per frame was not. Primary
  // branches only (depth>=3), matching the original glow's visual weight.
  if (depth >= 3) {
    ctx.save();
    ctx.globalAlpha = 0.16 + wave * 0.1;
    ctx.lineWidth = ctx.lineWidth + 3 + depth;
    ctx.strokeStyle = "rgba(94,151,232,0.9)";
    ctx.stroke();
    ctx.restore();
  }

  if (depth === 1) {
    const firePhase = 0.5 + 0.5 * Math.sin(Math.max(0, t) * 1.8 * Math.PI * 2 + seed);
    ctx.beginPath();
    ctx.arc(x2, y2, 1.9 + firePhase * 1.3, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(46,106,190,${0.7 + firePhase * 0.3})`;
    ctx.fill();
  }

  const nBranches = depth > 3 ? 3 : 2;
  for (let i = 0; i < nBranches; i++) {
    const childSeed = seed * 1.31 + i * 7.77 + depth;
    const spread = 0.5 + ((childSeed % 10) / 10) * 0.35;
    const angleOffset = (i - (nBranches - 1) / 2) * spread;
    drawNeuronBranch(ctx, x2, y2, a + angleOffset, length * 0.72, depth - 1, t, childSeed);
  }
}

type Props = {
  particleCount?: number;
  rootX?: number;
  rootY?: number;
  className?: string;
};

// 8 primaries fanning upward across a -2.62..-0.58 rad arc, per
// design-system/MASTER.md section 4b: the soma sits below the bottom edge
// and the structure grows into the page from beneath the fold.
const ROOT_ARC_START = -2.62;
const ROOT_ARC_END = -0.58;
const ROOT_COUNT = 8;
const ROOT_ANGLES = Array.from({ length: ROOT_COUNT }, (_, i) =>
  ROOT_ARC_START + ((ROOT_ARC_END - ROOT_ARC_START) * i) / (ROOT_COUNT - 1)
);

function useNeuronCanvas(
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
  particleCount: number,
  rootX: number,
  rootY: number
) {
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let width = 0;
    let height = 0;

    const resize = () => {
      const rect = canvas.parentElement?.getBoundingClientRect();
      if (!rect) return;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      width = rect.width;
      height = rect.height;
    };
    resize();
    window.addEventListener("resize", resize);

    const particles: Particle[] = [];
    for (let i = 0; i < particleCount; i++) {
      particles.push({
        x: Math.random(),
        y: Math.random(),
        r: 0.6 + Math.random() * 2.2,
        vx: (Math.random() - 0.5) * 0.00009,
        vy: (Math.random() - 0.5) * 0.00009,
        phase: Math.random() * Math.PI * 2,
      });
    }

    let raf = 0;
    let visible = document.visibilityState === "visible";
    const start = performance.now();
    // ponytail: throttled to ~30fps (time-based, not frame-parity, so the
    // synchronous first call always draws) rather than the browser's native
    // 60fps - this scene is slow/ambient (multi-second sway and breathing
    // cycles), so the halved repaint rate isn't visible, and it roughly
    // halves the per-second cost of ~500 gradient+stroke calls across 8
    // recursive depth-5 branch trees. Upgrade path if a future pass needs
    // smoother motion: cut nBranches/depth instead, or move the glow to a
    // cached offscreen layer redrawn less often than the strokes.
    let lastDrawMs = -Infinity;
    const MIN_FRAME_INTERVAL_MS = 30;

    const renderFrame = (now: number) => {
      if (now - lastDrawMs < MIN_FRAME_INTERVAL_MS) {
        raf = requestAnimationFrame(renderFrame);
        return;
      }
      lastDrawMs = now;
      try {
        // The first rAF timestamp can predate `start` (captured just before
        // requestAnimationFrame was scheduled) - a negative t propagates into
        // negative radii and canvas throws IndexSizeError. Clamp at the source.
        const t = Math.max(0, (now - start) / 1000);
        if (!width || !height) return;
        ctx.clearRect(0, 0, width, height);

        const ox = width * rootX;
        const oy = height * rootY;

        // Ambient bloom breathing behind the structure.
        const bloomLen = 196;
        const breathe = 0.5 + 0.5 * Math.sin((reducedMotion ? 0 : t) * 0.42);
        const bloomR = bloomLen * (3.0 + 0.35 * breathe);
        const bloomAlpha = 0.06 + 0.1 * breathe;
        const bloom = ctx.createRadialGradient(ox, oy, 0, ox, oy, bloomR);
        bloom.addColorStop(0, `rgba(94,151,232,${bloomAlpha})`);
        bloom.addColorStop(1, "rgba(94,151,232,0)");
        ctx.fillStyle = bloom;
        ctx.beginPath();
        ctx.arc(ox, oy, bloomR, 0, Math.PI * 2);
        ctx.fill();

        particles.forEach((p) => {
          if (!reducedMotion) {
            p.x += p.vx;
            p.y += p.vy;
            if (p.x < 0) p.x = 1;
            if (p.x > 1) p.x = 0;
            if (p.y < 0) p.y = 1;
            if (p.y > 1) p.y = 0;
          }
          const px = p.x * width;
          const py = p.y * height;
          const alpha = 0.26 + 0.22 * Math.sin((reducedMotion ? 0 : t) * 0.5 + p.phase);
          ctx.beginPath();
          ctx.arc(px, py, p.r * 1.7, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(78,138,226,${Math.max(0, Math.min(0.48, alpha))})`;
          ctx.fill();
        });

        ctx.save();
        ctx.translate(ox, oy);
        const frameT = reducedMotion ? 0 : t;
        ROOT_ANGLES.forEach((a, i) => {
          drawNeuronBranch(ctx, 0, 0, a, 200, 5, frameT, i * 13.7 + 1);
        });
        const pulse = 0.5 + 0.5 * Math.sin(frameT * 0.8);
        const somaR = 5.5 + pulse * 1.2;
        const haloR = 52 + pulse * 16;
        const glow = ctx.createRadialGradient(0, 0, 0, 0, 0, haloR);
        glow.addColorStop(0, `rgba(94,151,232,${0.44 + 0.16 * pulse})`);
        glow.addColorStop(1, "rgba(94,151,232,0)");
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(0, 0, haloR, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowColor = "rgba(94,151,232,0.6)";
        ctx.shadowBlur = 18 + pulse * 8;
        ctx.fillStyle = "rgba(46,106,190,0.95)";
        ctx.beginPath();
        ctx.arc(0, 0, somaR, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.restore();
      } finally {
        raf = !reducedMotion && visible ? requestAnimationFrame(renderFrame) : 0;
      }
    };

    // Draw one frame synchronously at mount - a backgrounded document never
    // fires rAF, which would otherwise leave a blank hero. Its own `finally`
    // block schedules the next frame (when visible and motion isn't
    // reduced), so no separate requestAnimationFrame call is needed here -
    // adding one would start two parallel render loops.
    renderFrame(start);

    const handleVisibility = () => {
      visible = document.visibilityState === "visible";
      if (visible && !reducedMotion && !raf) {
        raf = requestAnimationFrame(renderFrame);
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", handleVisibility);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [canvasRef, particleCount, rootX, rootY]);
}

export function NeuronCanvas({ particleCount = 54, rootX = 0.7, rootY = 1.0, className }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useNeuronCanvas(canvasRef, particleCount, rootX, rootY);

  return <canvas ref={canvasRef} className={className ?? "absolute inset-0 h-full w-full"} aria-hidden="true" />;
}
