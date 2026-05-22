import { arcScanTxUrl } from "@/lib/arc";

interface Props { txHash: string; compact?: boolean; }

export function ArcTxLink({ txHash, compact = false }: Props) {
  if (!txHash) return null;
  return (
    <a
      href={arcScanTxUrl(txHash)}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-cyan-400 hover:text-cyan-300 transition-colors text-xs font-mono"
      title="View on ArcScan"
    >
      {compact ? (
        <span>↗</span>
      ) : (
        <>
          <span className="w-2 h-2 rounded-full bg-cyan-400 inline-block" />
          {txHash.slice(0, 8)}...{txHash.slice(-6)}
        </>
      )}
    </a>
  );
}
