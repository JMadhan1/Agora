interface CardProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
  glow?: boolean;
  style?: React.CSSProperties;
}

export function Card({ title, children, className = "", glow = false, style }: CardProps) {
  return (
    <div
      className={`sentinel-card p-4 ${glow ? "shadow-glow-cyan" : ""} ${className}`}
      style={style}>
      {title && (
        <h2 className="text-xs font-semibold uppercase tracking-widest mb-3"
          style={{ color: "var(--text-secondary)" }}>
          {title}
        </h2>
      )}
      {children}
    </div>
  );
}
