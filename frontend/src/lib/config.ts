export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

export const WS_URL = (() => {
  const base = API_URL.replace(/^https:\/\//, "wss://").replace(
    /^http:\/\//,
    "ws://"
  );
  return `${base}/ws`;
})();
