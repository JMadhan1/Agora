"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import type { Attestation } from "@/types";

interface Props { attestation: Attestation; }

export function ReasoningTrace({ attestation }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card title="Latest Reasoning Trace">
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-slate-400 text-xs">Trace Hash (SHA-256)</p>
            <p className="font-mono text-xs text-white mt-0.5 break-all">{attestation.trace_hash || "—"}</p>
          </div>
          <div>
            <p className="text-slate-400 text-xs">IPFS CID</p>
            {attestation.ipfs_cid ? (
              <a
                href={`https://gateway.irys.xyz/${attestation.ipfs_cid}`}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-xs text-purple-400 hover:text-purple-300 break-all"
              >
                {attestation.ipfs_cid}
              </a>
            ) : (
              <p className="text-xs text-slate-500">—</p>
            )}
          </div>
        </div>

        <Button
          variant="secondary"
          size="sm"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? "Hide" : "Show"} attestation details
        </Button>

        {expanded && (
          <pre className="bg-slate-900 border border-slate-700 rounded-lg p-4 text-xs text-slate-300 overflow-x-auto max-h-64 overflow-y-auto">
            {JSON.stringify({
              id: attestation.id,
              market_id: attestation.market_id,
              recommendation: attestation.recommendation,
              probability_estimate: attestation.probability_estimate,
              confidence: `${attestation.confidence}%`,
              arc_tx_hash: attestation.arc_tx_hash,
              arc_scan_url: attestation.arc_scan_url,
              arc_block_number: attestation.arc_block_number,
              trace_hash: attestation.trace_hash,
              ipfs_cid: attestation.ipfs_cid,
              timestamp: attestation.timestamp,
            }, null, 2)}
          </pre>
        )}
      </div>
    </Card>
  );
}
