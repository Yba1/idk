// frontend/src/components/section-glow.tsx
type Props = {
  children: React.ReactNode;
  className?: string;
};

// Wraps glass-panel content with a close, strong, section-local colored glow
// so backdrop-blur has real color to pick up (a faint sitewide wash alone
// reads as flat/opaque). Pattern lifted from the design mockup's Sourced
// Summary section, applied consistently to every glass-panel section.
export function SectionGlow({ children, className }: Props) {
  return (
    <div className="relative">
      <div
        className="absolute inset-0 z-0 pointer-events-none overflow-hidden rounded-[16px]"
        style={{
          WebkitMaskImage: "linear-gradient(to bottom, black 0%, black 45%, transparent 88%)",
          maskImage: "linear-gradient(to bottom, black 0%, black 45%, transparent 88%)",
        }}
        aria-hidden="true"
      >
        <span
          className="absolute rounded-full blur-3xl motion-safe:animate-[drift-a_30s_ease-in-out_infinite]"
          style={{
            top: 0,
            left: "5%",
            width: "42%",
            height: "60%",
            background: "radial-gradient(circle, oklch(0.6 0.19 296 / 0.4), transparent 72%)",
          }}
        />
        <span
          className="absolute rounded-full blur-3xl motion-safe:animate-[drift-b_34s_ease-in-out_infinite]"
          style={{
            top: "10%",
            right: "8%",
            width: "40%",
            height: "55%",
            background: "radial-gradient(circle, oklch(0.62 0.2 350 / 0.32), transparent 72%)",
          }}
        />
      </div>
      <div className={`relative z-10 ${className ?? ""}`}>{children}</div>
    </div>
  );
}
