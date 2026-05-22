import clsx from "clsx";

interface Props { grade: string; }

const colors: Record<string, string> = {
  A: "bg-green-900 text-green-300 border-green-700",
  B: "bg-cyan-900 text-cyan-300 border-cyan-700",
  C: "bg-yellow-900 text-yellow-300 border-yellow-700",
  D: "bg-orange-900 text-orange-300 border-orange-700",
};

export function ReputationBadge({ grade }: Props) {
  return (
    <span className={clsx(
      "inline-flex items-center justify-center w-8 h-8 rounded-full border-2 font-bold text-sm",
      colors[grade] || "bg-slate-800 text-slate-400 border-slate-600",
    )}>
      {grade}
    </span>
  );
}
