const ARC_EXPLORER = process.env.NEXT_PUBLIC_ARC_EXPLORER || "https://testnet.arcscan.app";

export function arcScanTxUrl(txHash: string): string {
  if (!txHash) return "#";
  return `${ARC_EXPLORER}/tx/${txHash}`;
}

export function arcScanAddressUrl(address: string): string {
  if (!address) return "#";
  return `${ARC_EXPLORER}/address/${address}`;
}

export function formatArcBlock(blockNumber: number | null): string {
  if (!blockNumber) return "—";
  return `#${blockNumber.toLocaleString()}`;
}
