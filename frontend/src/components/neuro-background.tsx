"use client";

import { useEffect, useRef, useState } from "react";

interface Node {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  baseOpacity: number;
  pulsePhase: number;
}

interface Connection {
  nodeA: Node;
  nodeB: Node;
  distance: number;
}

export function NeuroBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nodesRef = useRef<Node[]>([]);
  const connectionsRef = useRef<Connection[]>([]);
  const [reducedMotion] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const frameRef = useRef(0);

  const NODE_COUNT = 60;
  const CONNECTION_DISTANCE = 150;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    function initializeNodes() {
      const nodes: Node[] = [];
      const width = canvas!.clientWidth;
      const height = canvas!.clientHeight;

      for (let i = 0; i < NODE_COUNT; i++) {
        nodes.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.3,
          vy: (Math.random() - 0.5) * 0.3,
          radius: Math.random() * 1.5 + 0.5,
          baseOpacity: Math.random() * 0.4 + 0.3,
          pulsePhase: Math.random() * Math.PI * 2,
        });
      }
      nodesRef.current = nodes;
    }

    function updateConnections() {
      const connections: Connection[] = [];
      const nodes = nodesRef.current;

      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const distance = Math.sqrt(dx * dx + dy * dy);

          if (distance < CONNECTION_DISTANCE) {
            connections.push({
              nodeA: nodes[i],
              nodeB: nodes[j],
              distance,
            });
          }
        }
      }
      connectionsRef.current = connections;
    }

    function resize() {
      const width = canvas!.clientWidth;
      const height = canvas!.clientHeight;
      const dpr = window.devicePixelRatio || 1;
      canvas!.width = width * dpr;
      canvas!.height = height * dpr;
      const resizeCtx = canvas!.getContext("2d");
      if (resizeCtx) {
        resizeCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
      }
      initializeNodes();
      updateConnections();
    }

    resize();
    const observer = new ResizeObserver(() => {
      resize();
    });
    observer.observe(canvas);

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    function draw() {
      const width = canvas!.clientWidth;
      const height = canvas!.clientHeight;
      const nodes = nodesRef.current;
      const connections = connectionsRef.current;

      ctx!.clearRect(0, 0, width, height);
      ctx!.globalCompositeOperation = "lighter";

      if (!reducedMotion) {
        for (const node of nodes) {
          node.x += node.vx;
          node.y += node.vy;
          node.pulsePhase += 0.015;

          if (node.x < 0) {
            node.x = width;
          } else if (node.x > width) {
            node.x = 0;
          }
          if (node.y < 0) {
            node.y = height;
          } else if (node.y > height) {
            node.y = 0;
          }
        }

        for (const conn of connections) {
          const opacity = (1 - conn.distance / CONNECTION_DISTANCE) * 0.15;
          ctx!.strokeStyle = `rgba(190, 140, 255, ${opacity})`;
          ctx!.lineWidth = 0.8;
          ctx!.beginPath();
          ctx!.moveTo(conn.nodeA.x, conn.nodeA.y);
          ctx!.lineTo(conn.nodeB.x, conn.nodeB.y);
          ctx!.stroke();
        }
      } else {
        for (const conn of connections) {
          const opacity = (1 - conn.distance / CONNECTION_DISTANCE) * 0.15;
          ctx!.strokeStyle = `rgba(190, 140, 255, ${opacity})`;
          ctx!.lineWidth = 0.8;
          ctx!.beginPath();
          ctx!.moveTo(conn.nodeA.x, conn.nodeA.y);
          ctx!.lineTo(conn.nodeB.x, conn.nodeB.y);
          ctx!.stroke();
        }
      }

      for (const node of nodes) {
        const pulseAmount = Math.sin(node.pulsePhase) * 0.2 + 0.8;
        const opacity = node.baseOpacity * pulseAmount;
        ctx!.fillStyle = `rgba(190, 140, 255, ${opacity})`;
        ctx!.beginPath();
        ctx!.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
        ctx!.fill();

        const glowOpacity = opacity * 0.4;
        ctx!.fillStyle = `rgba(255, 143, 198, ${glowOpacity})`;
        ctx!.beginPath();
        ctx!.arc(node.x, node.y, node.radius * 2.5, 0, Math.PI * 2);
        ctx!.fill();
      }

      ctx!.globalCompositeOperation = "source-over";

      frameRef.current = requestAnimationFrame(draw);
    }

    frameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frameRef.current);
  }, [reducedMotion]);

  return (
    <div className="fixed inset-0 -z-10 opacity-40">
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full"
        role="img"
        aria-label="Animated neural network background"
      />
    </div>
  );
}
