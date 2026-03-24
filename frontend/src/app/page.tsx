"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import {
  ArrowRight,
  ArrowDown,
  ChevronDown,
  X as XIcon,
  Check,
  Clock,
  Brain,
  ShieldAlert,
  Eye,
  Minus,
} from "lucide-react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import LoadingScreen from "@/components/landing/LoadingScreen";
import KaraokeText from "@/components/landing/KaraokeText";
import FeatureBeams from "@/components/landing/FeatureBeams";
import StackedCards from "@/components/landing/StackedCards";
import StatsCounter from "@/components/landing/StatsCounter";
import Testimonials from "@/components/landing/Testimonials";

gsap.registerPlugin(ScrollTrigger);

const ThreeScene = dynamic(
  () => import("@/components/landing/ThreeScene"),
  { ssr: false }
);

// ── Stats data ──────────────────────────────────────────────

const STATS = [
  { value: 6, suffix: "", label: "Pairs Scanned" },
  { value: 3, suffix: "", label: "Timeframes (H4, H1, M15)" },
  { value: 8, suffix: "", label: "Risk Checks Per Trade" },
  { value: 10, suffix: "s", label: "Kill Switch (Emergency Halt)" },
];

// ── Pain points data ────────────────────────────────────────

const PAIN_POINTS = [
  {
    icon: Clock,
    title: "Staring at charts 16 hours a day",
    description:
      "Miss one setup while sleeping and your whole week is negative.",
  },
  {
    icon: Brain,
    title: "Emotional decisions killing your P&L",
    description:
      "Revenge trading after a loss, cutting winners short, moving stop losses.",
  },
  {
    icon: ShieldAlert,
    title: "No systematic risk management",
    description:
      "One bad trade wipes out a month of gains. No circuit breaker, no daily limits.",
  },
  {
    icon: Eye,
    title: "Black-box trading bots you can't trust",
    description:
      "No explanation for why it entered a trade. No way to verify the logic.",
  },
];

const WHAT_IF_LINES = [
  "What if your trading ran 24/7 with zero emotion?",
  "What if every trade came with a plain-English explanation?",
  "What if risk was managed automatically with 8 independent checks?",
];

// ── Comparison data ─────────────────────────────────────────

interface ComparisonRow {
  feature: string;
  lumitrade: boolean | "partial";
  manual: boolean | "partial" | "na";
  bots: boolean | "partial";
}

const COMPARISONS: ComparisonRow[] = [
  { feature: "Explainable AI reasoning", lumitrade: true, manual: "na", bots: false },
  { feature: "24/7 automated scanning", lumitrade: true, manual: false, bots: true },
  { feature: "8-check risk validation", lumitrade: true, manual: false, bots: false },
  { feature: "Plain-English trade summaries", lumitrade: true, manual: false, bots: false },
  { feature: "Emergency kill switch (<10s)", lumitrade: true, manual: "na", bots: false },
  { feature: "Crash recovery + failover", lumitrade: true, manual: false, bots: false },
  { feature: "Real-time position monitoring", lumitrade: true, manual: "partial", bots: "partial" },
  { feature: "Full audit trail", lumitrade: true, manual: false, bots: "partial" },
];

// ── Pricing data ────────────────────────────────────────────

interface PricingTier {
  name: string;
  price: string;
  period: string;
  description: string;
  features: string[];
  cta: string;
  featured: boolean;
}

const PRICING: PricingTier[] = [
  {
    name: "Paper",
    price: "Free",
    period: "",
    description: "Prove the strategy risk-free before going live.",
    features: [
      "6 currency pairs",
      "15-minute signal intervals",
      "Full dashboard access",
      "Paper trading only",
      "Community support",
    ],
    cta: "Start Free",
    featured: false,
  },
  {
    name: "Pro",
    price: "$29",
    period: "/mo",
    description: "Live trading with priority AI and real-time alerts.",
    features: [
      "Everything in Paper",
      "Live trading enabled",
      "5-minute signal intervals",
      "Priority Claude AI calls",
      "Email + SMS alerts",
      "Dedicated support",
    ],
    cta: "Get Started",
    featured: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "Tailored infrastructure for institutional needs.",
    features: [
      "Everything in Pro",
      "Custom pair configuration",
      "API access",
      "White-label dashboard",
      "SLA guarantee",
      "Dedicated account manager",
    ],
    cta: "Contact Sales",
    featured: false,
  },
];

// ── FAQ data ────────────────────────────────────────────────

interface FAQItem {
  question: string;
  answer: string;
}

const FAQS: FAQItem[] = [
  {
    question: "Is this a black-box trading bot?",
    answer:
      "No. Every signal includes a plain-English explanation of why the trade was generated, including the specific indicators, timeframe confluence, and risk factors that contributed to the decision.",
  },
  {
    question: "How much money do I need to start?",
    answer:
      "Paper trading is completely free with a practice account. When you're ready to go live, we recommend starting with $100 and 0.5% risk per trade. The system is designed to protect capital first.",
  },
  {
    question: "What happens if the system crashes?",
    answer:
      "Lumitrade has automatic crash recovery, position reconciliation, and a distributed lock system to prevent duplicate trading. If the primary instance fails, the backup takes over within 3 minutes.",
  },
  {
    question: "Can I control when it trades?",
    answer:
      "Yes. You set the confidence threshold, risk per trade, daily loss limit, and maximum positions. There's also a kill switch that halts all trading in under 10 seconds.",
  },
  {
    question: "What pairs does it trade?",
    answer:
      "EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, and NZD/USD. The AI scans all pairs on H4, H1, and M15 timeframes.",
  },
  {
    question: "How is this different from other trading bots?",
    answer:
      "Most bots are black boxes. Lumitrade uses Claude AI to generate signals with full reasoning, validates every trade through an 8-check risk engine, and provides complete transparency. You can read exactly why every trade was taken.",
  },
];

// ── Footer data ─────────────────────────────────────────────

const FOOTER_LINKS = {
  Product: ["Dashboard", "Signals", "Analytics", "Risk Engine"],
  Company: ["About", "Blog", "Careers", "Contact"],
  Legal: ["Privacy Policy", "Terms of Service", "Risk Disclosure"],
};

// ── Integration logos ───────────────────────────────────────

const INTEGRATIONS = ["OANDA", "Claude AI", "Supabase", "Railway"];

// ── Helper: comparison cell icon ────────────────────────────

function ComparisonCell({ value }: { value: boolean | "partial" | "na" }) {
  if (value === true)
    return <Check size={18} style={{ color: "var(--color-brand)" }} />;
  if (value === false)
    return <XIcon size={18} style={{ color: "var(--color-text-tertiary)" }} />;
  if (value === "partial")
    return <Minus size={18} style={{ color: "var(--color-text-tertiary)" }} />;
  // na
  return (
    <span className="text-xs font-mono" style={{ color: "var(--color-text-tertiary)" }}>
      N/A
    </span>
  );
}

// ── FAQ Accordion Item ──────────────────────────────────────

function FAQAccordion({
  item,
  isOpen,
  onToggle,
}: {
  item: FAQItem;
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <div
      className="glass cursor-pointer"
      style={{ borderRadius: "var(--card-radius)" }}
      onClick={onToggle}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onToggle();
        }
      }}
    >
      <div className="flex items-center justify-between p-5 md:p-6">
        <span
          className="font-medium text-sm md:text-base pr-4"
          style={{ color: "var(--color-text-primary)" }}
        >
          {item.question}
        </span>
        <ChevronDown
          size={18}
          className="shrink-0 transition-transform duration-300"
          style={{
            color: "var(--color-text-tertiary)",
            transform: isOpen ? "rotate(180deg)" : "rotate(0deg)",
          }}
        />
      </div>
      <div className={`faq-content ${isOpen ? "open" : ""}`}>
        <p
          className="px-5 md:px-6 pb-5 md:pb-6 text-sm leading-relaxed"
          style={{ color: "var(--color-text-secondary)" }}
        >
          {item.answer}
        </p>
      </div>
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────────

export default function LandingPage() {
  const [loadingComplete, setLoadingComplete] = useState(false);
  const [showContent, setShowContent] = useState(false);
  const [scrolledPastTop, setScrolledPastTop] = useState(false);
  const [openFAQ, setOpenFAQ] = useState<number | null>(null);

  const heroContentRef = useRef<HTMLDivElement>(null);
  const mainContentRef = useRef<HTMLDivElement>(null);

  // Scroll listener for nav border
  useEffect(() => {
    const handleScroll = () => {
      setScrolledPastTop(window.scrollY > 10);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // GSAP: Hero content fade on scroll
  useEffect(() => {
    if (!showContent || !heroContentRef.current) return;

    const ctx = gsap.context(() => {
      gsap.to(heroContentRef.current, {
        opacity: 0,
        y: -60,
        scrollTrigger: {
          trigger: "#hero-spacer",
          start: "top top",
          end: "30% top",
          scrub: 1,
        },
      });
    });

    return () => ctx.revert();
  }, [showContent]);

  // GSAP: Main content reveal
  useEffect(() => {
    if (!showContent || !mainContentRef.current) return;

    const ctx = gsap.context(() => {
      // Reveal sections on scroll
      const sections = mainContentRef.current?.querySelectorAll(".reveal-section");
      sections?.forEach((section) => {
        gsap.fromTo(
          section,
          { opacity: 0, y: 40, filter: "blur(5px)" },
          {
            opacity: 1,
            y: 0,
            filter: "blur(0px)",
            duration: 1,
            ease: "power3.out",
            scrollTrigger: {
              trigger: section,
              start: "top 85%",
              end: "top 60%",
              toggleActions: "play none none none",
            },
          }
        );
      });

      // Stagger reveals
      const staggerEls = mainContentRef.current?.querySelectorAll(".stagger-reveal");
      staggerEls?.forEach((el) => {
        ScrollTrigger.create({
          trigger: el,
          start: "top 85%",
          onEnter: () => el.classList.add("active"),
        });
      });
    }, mainContentRef);

    return () => ctx.revert();
  }, [showContent]);

  const handleLoadingComplete = () => {
    setLoadingComplete(true);
    // Small delay to let the Three.js scene render before showing content
    setTimeout(() => setShowContent(true), 100);
  };

  const toggleFAQ = useCallback((index: number) => {
    setOpenFAQ((prev) => (prev === index ? null : index));
  }, []);

  return (
    <div className="min-h-[100dvh] relative" style={{ backgroundColor: "transparent" }}>
      {/* ── Loading Screen ──────────────────────────────── */}
      {!loadingComplete && <LoadingScreen onComplete={handleLoadingComplete} />}

      {/* ── Three.js Background ─────────────────────────── */}
      <ThreeScene visible={loadingComplete} />

      {/* ── Navigation ──────────────────────────────────── */}
      <nav
        className="fixed top-0 w-full z-50 transition-all duration-300"
        style={{
          backgroundColor: scrolledPastTop ? "rgba(13, 27, 42, 0.8)" : "transparent",
          backdropFilter: scrolledPastTop ? "blur(16px)" : "none",
          WebkitBackdropFilter: scrolledPastTop ? "blur(16px)" : "none",
          borderBottom: scrolledPastTop
            ? "1px solid rgba(255, 255, 255, 0.05)"
            : "1px solid transparent",
          opacity: showContent ? 1 : 0,
          transition:
            "opacity 0.6s ease, background-color 0.3s ease, backdrop-filter 0.3s ease, border-bottom 0.3s ease",
        }}
      >
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          {/* Left: Logo */}
          <div className="flex items-center gap-2.5">
            <div
              className="w-2 h-2 rounded-full"
              style={{
                backgroundColor: "#00C896",
                boxShadow: "0 0 8px rgba(0, 200, 150, 0.5)",
              }}
            />
            <span
              className="font-display font-semibold text-sm tracking-wide"
              style={{ color: "#FFFFFF" }}
            >
              LUMITRADE
            </span>
          </div>

          {/* Center: Nav links */}
          <div className="hidden md:flex items-center gap-8">
            {["Features", "Method", "Pricing"].map((item) => (
              <a
                key={item}
                href={`#${item.toLowerCase()}`}
                className="text-sm transition-colors duration-200 hover:text-white"
                style={{ color: "#6B7280" }}
              >
                {item}
              </a>
            ))}
          </div>

          {/* Right: CTAs */}
          <div className="flex items-center gap-4">
            <Link
              href="/auth/login"
              className="text-sm transition-colors duration-200 hover:text-white hidden sm:block"
              style={{ color: "#8A9BC0" }}
            >
              Log in
            </Link>
            <Link
              href="/auth/signup"
              className="px-5 py-2 text-sm font-medium rounded-full transition-all duration-200"
              style={{
                backgroundColor: "rgba(255, 255, 255, 0.08)",
                color: "#FFFFFF",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                minHeight: 44,
                display: "flex",
                alignItems: "center",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.backgroundColor =
                  "rgba(255, 255, 255, 0.12)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.backgroundColor =
                  "rgba(255, 255, 255, 0.08)";
              }}
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero Content (fixed overlay) ────────────────── */}
      <div
        ref={heroContentRef}
        className="fixed inset-0 z-10 flex items-center pointer-events-none"
        style={{
          opacity: showContent ? 1 : 0,
          transition: "opacity 0.8s cubic-bezier(0.16, 1, 0.3, 1)",
        }}
      >
        <div className="max-w-7xl mx-auto px-6 w-full">
          <div className="max-w-2xl">
            {/* Status pill */}
            <div
              className="inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full mb-8 pointer-events-auto"
              style={{
                border: "1px solid rgba(0, 200, 150, 0.15)",
                backgroundColor: "rgba(0, 200, 150, 0.04)",
              }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full animate-pulse"
                style={{ backgroundColor: "#00C896" }}
              />
              <span className="font-mono text-xs" style={{ color: "#8A9BC0" }}>
                v1.0 — Paper Trading Live
              </span>
            </div>

            {/* Headline */}
            <h1
              className="font-display font-bold tracking-tight mb-6 text-5xl md:text-7xl lg:text-8xl leading-[0.95]"
              style={{ color: "#FFFFFF" }}
            >
              Trade forex with
              <br />
              <span
                style={{
                  background: "linear-gradient(135deg, #00C896, #3D8EFF)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                }}
              >
                AI precision.
              </span>
            </h1>

            {/* Subtext */}
            <p
              className="text-lg md:text-xl max-w-xl mb-10 leading-relaxed"
              style={{ color: "#8A9BC0" }}
            >
              Lumitrade uses Claude AI to scan 6 forex pairs across 3
              timeframes, generate explainable signals with confidence scores,
              and execute trades through OANDA — all while managing risk with 8
              independent safety checks.
            </p>

            {/* CTAs */}
            <div className="flex flex-col sm:flex-row gap-4 pointer-events-auto">
              <Link
                href="/auth/signup"
                className="inline-flex items-center justify-center gap-2.5 px-8 py-4 font-semibold rounded-full text-base transition-all duration-200"
                style={{
                  backgroundColor: "#00C896",
                  color: "#0D1B2A",
                  minHeight: 52,
                  boxShadow:
                    "0 0 30px rgba(0, 200, 150, 0.2), 0 4px 12px rgba(0, 0, 0, 0.3)",
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.boxShadow =
                    "0 0 40px rgba(0, 200, 150, 0.35), 0 4px 12px rgba(0, 0, 0, 0.3)";
                  (e.currentTarget as HTMLElement).style.transform =
                    "translateY(-1px)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.boxShadow =
                    "0 0 30px rgba(0, 200, 150, 0.2), 0 4px 12px rgba(0, 0, 0, 0.3)";
                  (e.currentTarget as HTMLElement).style.transform =
                    "translateY(0)";
                }}
              >
                Start Paper Trading <ArrowRight size={18} />
              </Link>
              <a
                href="#features"
                className="inline-flex items-center justify-center gap-2.5 px-8 py-4 font-medium rounded-full text-base transition-all duration-200"
                style={{
                  backgroundColor: "rgba(255, 255, 255, 0.05)",
                  color: "#FFFFFF",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  minHeight: 52,
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.backgroundColor =
                    "rgba(255, 255, 255, 0.08)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.backgroundColor =
                    "rgba(255, 255, 255, 0.05)";
                }}
              >
                View Documentation <ArrowDown size={16} />
              </a>
            </div>
          </div>
        </div>

        {/* Bounce arrow at bottom */}
        <div
          className="absolute bottom-12 left-1/2 -translate-x-1/2"
          style={{ animation: "bounce-subtle 2s ease-in-out infinite" }}
        >
          <ChevronDown size={24} style={{ color: "#6B7280" }} />
        </div>
      </div>

      {/* ── Hero Scroll Spacer (drives 3D scene) ────────── */}
      <div id="hero-spacer" style={{ height: "400vh" }} />

      {/* ── Main Content ────────────────────────────────── */}
      <div
        ref={mainContentRef}
        className="relative z-20"
        style={{ backgroundColor: "rgba(13, 27, 42, 0.35)" }}
      >
        {/* Gradient transition from 3D scene */}
        <div
          className="h-32 -mt-32 relative z-20"
          style={{
            background: "linear-gradient(to bottom, transparent, rgba(13, 27, 42, 0.35))",
          }}
        />

        {/* ── SECTION A: Pain Points ──────────────────────── */}
        <section className="py-24 md:py-32 px-6 reveal-section">
          <div className="max-w-6xl mx-auto">
            <div className="mb-16">
              <p
                className="text-xs font-mono uppercase tracking-widest mb-4"
                style={{ color: "var(--color-brand)" }}
              >
                The Problem
              </p>
              <h2
                className="text-3xl md:text-5xl font-display font-bold tracking-tight leading-tight max-w-3xl"
                style={{ color: "var(--color-text-primary)" }}
              >
                Manual trading is a full-time job that pays part-time results.
              </h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
              {/* Left column - pain points */}
              <div className="space-y-8 stagger-reveal">
                {PAIN_POINTS.map((point) => (
                  <div key={point.title} className="flex gap-4">
                    <div
                      className="shrink-0 w-10 h-10 rounded-lg flex items-center justify-center"
                      style={{
                        backgroundColor: "rgba(255, 77, 106, 0.08)",
                        border: "1px solid rgba(255, 77, 106, 0.12)",
                      }}
                    >
                      <XIcon size={18} style={{ color: "#FF4D6A" }} />
                    </div>
                    <div>
                      <p
                        className="font-medium text-base mb-1"
                        style={{ color: "var(--color-text-primary)" }}
                      >
                        {point.title}
                      </p>
                      <p
                        className="text-sm leading-relaxed"
                        style={{ color: "var(--color-text-secondary)" }}
                      >
                        {point.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
              {/* Right column - solution teaser */}
              <div
                className="glass rounded-2xl p-8 relative overflow-hidden flex flex-col justify-center"
                style={{ borderRadius: 16 }}
              >
                {/* Subtle glow behind */}
                <div
                  className="absolute -top-20 -right-20 w-60 h-60 rounded-full pointer-events-none"
                  style={{
                    background:
                      "radial-gradient(circle, rgba(0, 200, 150, 0.06), transparent 70%)",
                  }}
                />
                <p
                  className="font-display font-bold text-xl mb-8"
                  style={{ color: "var(--color-text-primary)" }}
                >
                  What if instead...
                </p>
                <div className="space-y-5 stagger-reveal">
                  {WHAT_IF_LINES.map((line) => (
                    <div key={line} className="flex items-start gap-3">
                      <div
                        className="shrink-0 w-6 h-6 rounded-full flex items-center justify-center mt-0.5"
                        style={{
                          backgroundColor: "rgba(0, 200, 150, 0.1)",
                          border: "1px solid rgba(0, 200, 150, 0.2)",
                        }}
                      >
                        <Check size={14} style={{ color: "var(--color-brand)" }} />
                      </div>
                      <p
                        className="text-sm leading-relaxed"
                        style={{ color: "var(--color-text-secondary)" }}
                      >
                        {line}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── Karaoke Text Section ───────────────────────── */}
        <section className="py-24 md:py-32 px-6 reveal-section" id="features">
          <KaraokeText text="Stop guessing market direction. Stop staring at charts for 16 hours a day. Lumitrade's AI engine reads multi-timeframe price action across 6 major pairs, validates against eight independent risk checks, sizes positions based on your account equity, and executes with millisecond precision on OANDA — all while you sleep." />
        </section>

        {/* ── Feature Beams Section ──────────────────────── */}
        <section className="py-24 md:py-32 reveal-section">
          <FeatureBeams />
        </section>

        {/* ── SECTION B: Integration Logos ─────────────────── */}
        <section
          className="py-16 px-6 reveal-section"
          style={{
            borderTop: "1px solid var(--color-border)",
            borderBottom: "1px solid var(--color-border)",
          }}
        >
          <div className="max-w-5xl mx-auto">
            <p
              className="text-center text-xs uppercase tracking-widest mb-8"
              style={{ color: "var(--color-text-tertiary)" }}
            >
              Powered by industry-leading infrastructure
            </p>
            <div className="flex flex-wrap justify-center items-center gap-12 md:gap-16">
              {INTEGRATIONS.map((name) => (
                <div
                  key={name}
                  className="flex items-center gap-2 opacity-40 hover:opacity-70 transition-opacity duration-300"
                >
                  <span
                    className="text-lg font-bold tracking-tight"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    {name}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Stacked Cards (The Lumitrade Method) ────────── */}
        <section id="method">
          <StackedCards />
        </section>

        {/* ── SECTION C: Comparison Table ──────────────────── */}
        <section className="py-24 md:py-32 px-6 reveal-section">
          <div className="max-w-4xl mx-auto">
            <div className="text-center mb-16">
              <p
                className="text-xs font-mono uppercase tracking-widest mb-4"
                style={{ color: "var(--color-brand)" }}
              >
                Why Lumitrade
              </p>
              <h2
                className="text-3xl md:text-4xl font-display font-bold tracking-tight"
                style={{ color: "var(--color-text-primary)" }}
              >
                Not another black-box trading bot.
              </h2>
            </div>
            <div className="glass rounded-2xl overflow-hidden" style={{ borderRadius: 16 }}>
              <div className="overflow-x-auto">
                <table className="w-full text-sm min-w-[500px]">
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--color-border)" }}>
                      <th
                        className="text-left p-5 font-medium"
                        style={{ color: "var(--color-text-secondary)" }}
                      >
                        Feature
                      </th>
                      <th
                        className="p-5 font-semibold"
                        style={{ color: "var(--color-brand)" }}
                      >
                        Lumitrade
                      </th>
                      <th
                        className="p-5 font-medium"
                        style={{ color: "var(--color-text-tertiary)" }}
                      >
                        Manual Trading
                      </th>
                      <th
                        className="p-5 font-medium"
                        style={{ color: "var(--color-text-tertiary)" }}
                      >
                        Generic Bots
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {COMPARISONS.map((row, i) => (
                      <tr
                        key={row.feature}
                        style={{
                          borderBottom:
                            i < COMPARISONS.length - 1
                              ? "1px solid var(--color-border)"
                              : "none",
                        }}
                      >
                        <td
                          className="p-5 font-medium"
                          style={{ color: "var(--color-text-primary)" }}
                        >
                          {row.feature}
                        </td>
                        <td className="p-5">
                          <div className="flex justify-center">
                            <ComparisonCell value={row.lumitrade} />
                          </div>
                        </td>
                        <td className="p-5">
                          <div className="flex justify-center">
                            <ComparisonCell value={row.manual} />
                          </div>
                        </td>
                        <td className="p-5">
                          <div className="flex justify-center">
                            <ComparisonCell value={row.bots} />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        {/* ── Stats Section ──────────────────────────────── */}
        <section className="py-24 md:py-32 px-6 reveal-section">
          <div className="max-w-4xl mx-auto">
            <StatsCounter stats={STATS} />
          </div>
        </section>

        {/* ── SECTION D: Pricing ──────────────────────────── */}
        <section className="py-24 md:py-32 px-6 reveal-section" id="pricing">
          <div className="max-w-5xl mx-auto">
            <div className="text-center mb-16">
              <p
                className="text-xs font-mono uppercase tracking-widest mb-4"
                style={{ color: "var(--color-brand)" }}
              >
                Pricing
              </p>
              <h2
                className="text-3xl md:text-4xl font-display font-bold tracking-tight"
                style={{ color: "var(--color-text-primary)" }}
              >
                Start free. Scale when ready.
              </h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-4 items-center">
              {PRICING.map((tier) => (
                <div
                  key={tier.name}
                  className={`relative rounded-2xl p-8 ${tier.featured ? "md:-my-4 md:py-12" : ""}`}
                  style={{
                    background: tier.featured
                      ? "var(--color-bg-surface)"
                      : "var(--color-bg-surface)",
                    border: tier.featured
                      ? "1px solid rgba(0, 200, 150, 0.25)"
                      : "1px solid var(--color-border)",
                    borderRadius: 16,
                    backdropFilter: "blur(16px)",
                    WebkitBackdropFilter: "blur(16px)",
                    boxShadow: tier.featured
                      ? "0 0 60px rgba(0, 200, 150, 0.08), 0 4px 24px rgba(0, 0, 0, 0.4)"
                      : "0 4px 24px rgba(0, 0, 0, 0.4)",
                  }}
                >
                  {/* Featured glow */}
                  {tier.featured && (
                    <div
                      className="absolute -top-px -left-px -right-px -bottom-px rounded-2xl pointer-events-none"
                      style={{
                        background:
                          "linear-gradient(135deg, rgba(0, 200, 150, 0.1), transparent 50%)",
                        borderRadius: 16,
                      }}
                    />
                  )}
                  <div className="relative">
                    <p
                      className="text-xs font-mono uppercase tracking-widest mb-2"
                      style={{
                        color: tier.featured
                          ? "var(--color-brand)"
                          : "var(--color-text-tertiary)",
                      }}
                    >
                      {tier.name}
                    </p>
                    <div className="flex items-baseline gap-1 mb-2">
                      <span
                        className="font-display font-bold text-4xl"
                        style={{ color: "var(--color-text-primary)" }}
                      >
                        {tier.price}
                      </span>
                      {tier.period && (
                        <span
                          className="text-sm"
                          style={{ color: "var(--color-text-tertiary)" }}
                        >
                          {tier.period}
                        </span>
                      )}
                    </div>
                    <p
                      className="text-sm mb-8 leading-relaxed"
                      style={{ color: "var(--color-text-secondary)" }}
                    >
                      {tier.description}
                    </p>
                    <ul className="space-y-3 mb-8">
                      {tier.features.map((feature) => (
                        <li key={feature} className="flex items-center gap-3">
                          <Check
                            size={16}
                            style={{
                              color: tier.featured
                                ? "var(--color-brand)"
                                : "var(--color-text-tertiary)",
                            }}
                          />
                          <span
                            className="text-sm"
                            style={{ color: "var(--color-text-secondary)" }}
                          >
                            {feature}
                          </span>
                        </li>
                      ))}
                    </ul>
                    <Link
                      href={tier.name === "Enterprise" ? "#" : "/auth/signup"}
                      className="w-full inline-flex items-center justify-center gap-2 px-6 py-3.5 font-semibold rounded-full text-sm transition-all duration-200"
                      style={{
                        backgroundColor: tier.featured ? "#00C896" : "rgba(255, 255, 255, 0.06)",
                        color: tier.featured ? "#0D1B2A" : "var(--color-text-primary)",
                        border: tier.featured
                          ? "none"
                          : "1px solid rgba(255, 255, 255, 0.08)",
                        minHeight: 48,
                        boxShadow: tier.featured
                          ? "0 0 24px rgba(0, 200, 150, 0.2)"
                          : "none",
                      }}
                      onMouseEnter={(e) => {
                        if (tier.featured) {
                          (e.currentTarget as HTMLElement).style.boxShadow =
                            "0 0 36px rgba(0, 200, 150, 0.35)";
                          (e.currentTarget as HTMLElement).style.transform =
                            "translateY(-1px)";
                        } else {
                          (e.currentTarget as HTMLElement).style.backgroundColor =
                            "rgba(255, 255, 255, 0.1)";
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (tier.featured) {
                          (e.currentTarget as HTMLElement).style.boxShadow =
                            "0 0 24px rgba(0, 200, 150, 0.2)";
                          (e.currentTarget as HTMLElement).style.transform =
                            "translateY(0)";
                        } else {
                          (e.currentTarget as HTMLElement).style.backgroundColor =
                            "rgba(255, 255, 255, 0.06)";
                        }
                      }}
                    >
                      {tier.cta}
                      {tier.featured && <ArrowRight size={16} />}
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Testimonials Section ────────────────────────── */}
        <section className="py-24 md:py-32 reveal-section">
          <Testimonials />
        </section>

        {/* ── SECTION E: FAQ ──────────────────────────────── */}
        <section className="py-24 md:py-32 px-6 reveal-section">
          <div className="max-w-3xl mx-auto">
            <div className="text-center mb-16">
              <p
                className="text-xs font-mono uppercase tracking-widest mb-4"
                style={{ color: "var(--color-brand)" }}
              >
                FAQ
              </p>
              <h2
                className="text-3xl md:text-4xl font-display font-bold tracking-tight"
                style={{ color: "var(--color-text-primary)" }}
              >
                Common questions, straight answers.
              </h2>
            </div>
            <div className="space-y-3">
              {FAQS.map((faq, i) => (
                <FAQAccordion
                  key={faq.question}
                  item={faq}
                  isOpen={openFAQ === i}
                  onToggle={() => toggleFAQ(i)}
                />
              ))}
            </div>
          </div>
        </section>

        {/* ── CTA Section (3D scene fades back) ──────────── */}
        <section
          id="cta-section"
          className="relative"
          style={{ height: "150vh" }}
        >
          <div className="sticky top-0 min-h-[100dvh] flex items-center justify-center px-6">
            {/* Fade to transparent so 3D scene shows through */}
            <div
              className="absolute inset-0"
              style={{
                background:
                  "linear-gradient(to bottom, #0D1B2A 0%, transparent 40%)",
                pointerEvents: "none",
              }}
            />

            <div className="relative z-10 text-center max-w-3xl">
              <h2
                className="font-display font-bold tracking-tight mb-6 text-5xl md:text-7xl lg:text-8xl leading-[0.95]"
                style={{ color: "#FFFFFF" }}
              >
                Trade Smarter.
                <br />
                <span style={{ color: "#8A9BC0" }}>Sleep Better.</span>
              </h2>

              <p
                className="text-lg md:text-xl mb-10 leading-relaxed max-w-xl mx-auto"
                style={{ color: "#6B7280" }}
              >
                Start with paper trading. Prove the strategy works. Switch to
                live when the data says you are ready.
              </p>

              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Link
                  href="/auth/signup"
                  className="inline-flex items-center justify-center gap-2.5 px-10 py-4 font-semibold rounded-full text-lg transition-all duration-200"
                  style={{
                    backgroundColor: "#FFFFFF",
                    color: "#0D1B2A",
                    minHeight: 56,
                    boxShadow: "0 4px 24px rgba(255, 255, 255, 0.1)",
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLElement).style.transform =
                      "translateY(-2px)";
                    (e.currentTarget as HTMLElement).style.boxShadow =
                      "0 8px 32px rgba(255, 255, 255, 0.15)";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLElement).style.transform =
                      "translateY(0)";
                    (e.currentTarget as HTMLElement).style.boxShadow =
                      "0 4px 24px rgba(255, 255, 255, 0.1)";
                  }}
                >
                  Get Started Free <ArrowRight size={20} />
                </Link>
                <a
                  href="#"
                  className="inline-flex items-center justify-center gap-2.5 px-10 py-4 font-medium rounded-full text-lg transition-all duration-200"
                  style={{
                    backgroundColor: "rgba(255, 255, 255, 0.05)",
                    color: "#FFFFFF",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                    minHeight: 56,
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLElement).style.backgroundColor =
                      "rgba(255, 255, 255, 0.08)";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLElement).style.backgroundColor =
                      "rgba(255, 255, 255, 0.05)";
                  }}
                >
                  Read the Docs
                </a>
              </div>
            </div>
          </div>
        </section>

        {/* ── Footer ─────────────────────────────────────── */}
        <footer
          className="relative z-30 py-16 px-6"
          style={{
            backgroundColor: "rgba(5, 5, 6, 0.5)",
            borderTop: "1px solid rgba(255, 255, 255, 0.04)",
          }}
        >
          <div className="max-w-6xl mx-auto">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-12 mb-16">
              {/* Logo + description */}
              <div className="lg:col-span-2">
                <div className="flex items-center gap-2.5 mb-4">
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{
                      backgroundColor: "#00C896",
                      boxShadow: "0 0 8px rgba(0, 200, 150, 0.4)",
                    }}
                  />
                  <span
                    className="font-display font-semibold text-sm tracking-wide"
                    style={{ color: "#FFFFFF" }}
                  >
                    LUMITRADE
                  </span>
                </div>
                <p
                  className="text-sm leading-relaxed max-w-sm mb-6"
                  style={{ color: "#6B7280" }}
                >
                  AI-powered forex trading platform with explainable signals,
                  disciplined risk management, and real-time execution via
                  OANDA.
                </p>
                <p className="text-xs" style={{ color: "#333" }}>
                  &copy; {new Date().getFullYear()} Lumitrade. All rights
                  reserved.
                </p>
              </div>

              {/* Link columns */}
              {Object.entries(FOOTER_LINKS).map(([category, links]) => (
                <div key={category}>
                  <p
                    className="font-display font-semibold text-xs uppercase tracking-widest mb-4"
                    style={{ color: "#6B7280" }}
                  >
                    {category}
                  </p>
                  <ul className="space-y-3">
                    {links.map((link) => (
                      <li key={link}>
                        <a
                          href="#"
                          className="text-sm transition-colors duration-200 hover:text-white"
                          style={{ color: "#6B7280" }}
                        >
                          {link}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>

            {/* Bottom bar */}
            <div
              className="pt-8 flex flex-col sm:flex-row items-center justify-between gap-4"
              style={{ borderTop: "1px solid rgba(255, 255, 255, 0.04)" }}
            >
              <p className="text-xs" style={{ color: "#333" }}>
                Trading forex involves risk of loss. Past performance does not
                guarantee future results.
              </p>
              <p className="font-mono text-xs" style={{ color: "#333" }}>
                v1.0.0
              </p>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
