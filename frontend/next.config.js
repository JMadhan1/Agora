/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_ARC_EXPLORER: "https://testnet.arcscan.app",
  },
};
module.exports = nextConfig;
