// frontend/src/components/neuron-canvas.tsx
"use client";

import { useEffect, useRef } from "react";

type Particle = {
  x: number;
  y: number;
  r: number;
  vx: number;
  vy: number;
  hue: "purple" | "gold";
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
  const opacity = 0.16 + depth * 0.09;

  const grad = ctx.createLinearGradient(x, y, x2, y2);
  grad.addColorStop(0, `rgba(214,178,255,${opacity})`);
  grad.addColorStop(1, `rgba(255,150,205,${opacity * 0.5})`);
  ctx.strokeStyle = grad;
  ctx.lineWidth = Math.max(0.6, depth * 0.85);

  ctx.beginPath();
  ctx.moveTo(x, y);
  const bend = Math.sin(t * 0.3 + seed * 1.7) * length * 0.12;
  const mx = (x + x2) / 2 + Math.cos(a + Math.PI / 2) * bend;
  const my = (y + y2) / 2 + Math.sin(a + Math.PI / 2) * bend;
  ctx.quadraticCurveTo(mx, my, x2, y2);
  ctx.stroke();

  if (depth === 1) {
    ctx.beginPath();
    ctx.arc(x2, y2, 1.4, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(255,220,240,0.5)";
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
        hue: Math.random() < 0.75 ? "purple" : "gold",
        phase: Math.random() * Math.PI * 2,
      });
    }

    let raf = 0;
    const start = performance.now();

    const renderFrame = (now: number) => {
      const t = (now - start) / 1000;
      if (!width || !height) return;
      ctx.clearRect(0, 0, width, height);

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
        const alpha = 0.25 + 0.2 * Math.sin((reducedMotion ? 0 : t) * 0.5 + p.phase);
        ctx.beginPath();
        ctx.arc(px, py, p.r * 2.4, 0, Math.PI * 2);
        ctx.fillStyle =
          p.hue === "purple" ? `rgba(190,140,255,${alpha * 0.5})` : `rgba(255,210,150,${alpha * 0.35})`;
        ctx.fill();
      });

      const ox = width * rootX;
      const oy = height * rootY;
      ctx.save();
      ctx.translate(ox, oy);
      const rootAngles = [-2.4, -1.5, -0.6, 0.3, 1.1, 2.0];
      const frameT = reducedMotion ? 0 : t;
      rootAngles.forEach((a, i) => {
        drawNeuronBranch(ctx, 0, 0, a, 95 + (i % 3) * 18, 5, frameT, i * 13.7 + 1);
      });
      const pulse = 0.5 + 0.5 * Math.sin(frameT * 0.8);
      const glow = ctx.createRadialGradient(0, 0, 0, 0, 0, 26 + 6 * pulse);
      glow.addColorStop(0, `rgba(230,190,255,${0.55 + 0.25 * pulse})`);
      glow.addColorStop(1, "rgba(230,190,255,0)");
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(0, 0, 26 + 6 * pulse, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      if (!reducedMotion) {
        raf = requestAnimationFrame(renderFrame);
      }
    };

    raf = requestAnimationFrame(renderFrame);
    if (reducedMotion) {
      renderFrame(start);
    }

    return () => {
      window.removeEventListener("resize", resize);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [canvasRef, particleCount, rootX, rootY]);
}

export function NeuronCanvas({ particleCount = 46, rootX = 0.68, rootY = 0.42, className }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useNeuronCanvas(canvasRef, particleCount, rootX, rootY);

  return <canvas ref={canvasRef} className={className ?? "absolute inset-0 h-full w-full"} aria-hidden="true" />;
}
