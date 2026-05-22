import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/layout/Navbar";
import { Sidebar } from "@/components/layout/Sidebar";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Oracle Sentinel — Autonomous AI Truth Verification",
  description:
    "Real-time prediction market manipulation detection. 3 AI agents, cryptographic attestations, Arc Testnet. Built for Agora Hackathon 2026.",
  keywords: "oracle, AI, prediction markets, blockchain, attestation, Arc, Polymarket",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} min-h-screen text-white antialiased`}
        style={{ backgroundColor: "var(--bg-primary)" }}>
        <div className="relative z-10">
          <Navbar />
          <div className="flex">
            <Sidebar />
            <main className="flex-1 ml-64 mt-16 min-h-[calc(100vh-4rem)] p-6 lg:p-8">
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
