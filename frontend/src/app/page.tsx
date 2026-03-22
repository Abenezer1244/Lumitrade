"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { ArrowRight, Shield, Brain, Zap, BarChart2, AlertTriangle } from "lucide-react";

const ScrollSequence = dynamic(
  () => import("@/components/landing/ScrollSequence"),
  { ssr: false }
);

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#0D1B2A]">
      {/* Nav */}
      <nav className="fixed top-0 w-full z-50 border-b border-[#1E3050] bg-[#0D1B2A]/90 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <span className="font-display text-xl font-semibold text-[#E67E22] tracking-wide">
            LUMITRADE
          </span>
          <div className="flex items-center gap-6">
            <Link href="/dashboard" className="text-sm text-[#8A9BC0] hover:text-[#E8F0FE] transition-colors">
              Dashboard
            </Link>
            <Link href="/dashboard" className="px-4 py-2 bg-[#3D8EFF] text-white text-sm font-medium rounded-md hover:bg-[#3D8EFF]/90 transition-colors">
              Launch App
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-32 pb-16 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[#2A4070] bg-[#1A2840] mb-6">
            <span className="w-2 h-2 rounded-full bg-[#00C896] animate-pulse" />
            <span className="text-xs text-[#8A9BC0]">Live on OANDA — Paper Trading Active</span>
          </div>
          <h1 className="text-5xl md:text-6xl font-display font-semibold text-[#E8F0FE] leading-tight mb-6">
            AI-Powered Forex Trading<br />
            <span className="text-[#3D8EFF]">You Can Trust</span>
          </h1>
          <p className="text-lg text-[#8A9BC0] max-w-2xl mx-auto mb-8 leading-relaxed">
            Lumitrade uses Claude AI to analyze multi-timeframe market data and generate
            explainable trading signals with disciplined risk management. Every decision
            comes with a plain-English summary.
          </p>
          <div className="flex justify-center gap-4">
            <Link href="/dashboard" className="inline-flex items-center gap-2 px-6 py-3 bg-[#3D8EFF] text-white font-medium rounded-lg hover:bg-[#3D8EFF]/90 transition-colors">
              Open Dashboard <ArrowRight size={16} />
            </Link>
            <a href="#demo" className="inline-flex items-center gap-2 px-6 py-3 border border-[#2A4070] text-[#8A9BC0] font-medium rounded-lg hover:border-[#3D8EFF] hover:text-[#E8F0FE] transition-colors">
              Watch it work
            </a>
          </div>
        </div>
      </section>

      {/* Scroll-driven terminal demo */}
      <section id="demo" className="py-16 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-8">
            <h2 className="text-2xl font-display text-[#E8F0FE] mb-2">See the Terminal Come Alive</h2>
            <p className="text-sm text-[#8A9BC0]">Scroll inside to watch data flow, signals generate, and trades execute</p>
          </div>
          <div className="rounded-xl border border-[#1E3050] overflow-hidden shadow-2xl shadow-[#3D8EFF]/5">
            <ScrollSequence />
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-display text-[#E8F0FE] text-center mb-12">Enterprise-Grade from Day One</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              { icon: Brain, title: "Explainable AI", desc: "Every signal includes plain-English reasoning and full indicator breakdown. No black boxes.", color: "#3D8EFF" },
              { icon: Shield, title: "Risk Engine", desc: "8-check validation pipeline. 2% max risk. Daily/weekly loss limits. Circuit breaker protection.", color: "#00C896" },
              { icon: Zap, title: "Real-Time Execution", desc: "Paper trading with real OANDA prices. Live trading after 50+ successful trades.", color: "#FFB347" },
              { icon: BarChart2, title: "Full Analytics", desc: "Win rate, profit factor, Sharpe ratio, equity curve. Per-pair and per-session breakdown.", color: "#3D8EFF" },
              { icon: AlertTriangle, title: "Kill Switch", desc: "Emergency halt in under 10 seconds. Two-step typed confirmation prevents accidents.", color: "#FF4D6A" },
              { icon: Shield, title: "Crash Recovery", desc: "Auto-restart, position reconciliation, local backup failover. Distributed lock prevents dual trading.", color: "#00C896" },
            ].map((feature, i) => (
              <div key={i} className="bg-[#111D2E] border border-[#1E3050] rounded-lg p-6 hover:border-[#2A4070] transition-colors">
                <feature.icon size={24} style={{ color: feature.color }} className="mb-4" />
                <h3 className="text-lg font-medium text-[#E8F0FE] mb-2">{feature.title}</h3>
                <p className="text-sm text-[#8A9BC0] leading-relaxed">{feature.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-6 border-t border-[#1E3050]">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-3xl font-display text-[#E8F0FE] mb-4">Ready to Trade Smarter?</h2>
          <p className="text-[#8A9BC0] mb-8">Start with paper trading. Prove the strategy works. Switch to live when the data says you are ready.</p>
          <Link href="/dashboard" className="inline-flex items-center gap-2 px-8 py-3 bg-[#3D8EFF] text-white font-medium rounded-lg hover:bg-[#3D8EFF]/90 transition-colors text-lg">
            Open Dashboard <ArrowRight size={18} />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[#1E3050] py-8 px-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between text-xs text-[#4A5E80]">
          <span>Lumitrade v1.0 — AI-Powered Forex Trading</span>
          <span>Phase 0: Personal Trading Tool</span>
        </div>
      </footer>
    </div>
  );
}
