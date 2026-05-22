import clsx from "clsx";

interface BadgeProps {
  variant?: "yes" | "no" | "uncertain" | "arc" | "default";
  children: React.ReactNode;
  className?: string;
}

const variants = {
  yes: "bg-green-900/60 text-green-300 border-green-700",
  no: "bg-red-900/60 text-red-300 border-red-700",
  uncertain: "bg-yellow-900/60 text-yellow-300 border-yellow-700",
  arc: "bg-cyan-900/60 text-cyan-300 border-cyan-700",
  default: "bg-slate-700 text-slate-300 border-slate-600",
};

export function Badge({ variant = "default", children, className }: BadgeProps) {
  return (
    <span className={clsx("inline-flex items-center px-2 py-0.5 text-xs font-medium rounded border", variants[variant], className)}>
      {children}
    </span>
  );
}
