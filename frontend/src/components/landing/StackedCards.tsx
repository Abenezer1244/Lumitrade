"use client";

import { useEffect, useRef, useState } from "react";
import { Database, Brain, Zap } from "lucide-react";

interface CardData {
  step: string;
  title: string;
  description: string;
  icon: React.ElementType;
  iconColor: string;
  iconBg: string;
}

const CARDS: CardData[] = [
  {
    step: "01 // Ingestion",
    title: "Market Scanner",
    description:
      "Multi-timeframe candle data across 6 major pairs. H4, H1, and M15 indicators calculated in parallel. Regime detection classifies trending, ranging, or volatile conditions.",
    icon: Database,
    iconColor: "#00C896",
    iconBg: "rgba(0, 232, 157, 0.1)",
  },
  {
    step: "02 // Analysis",
    title: "AI Brain",
    description:
      "Claude AI receives structured market context and generates signals with confidence scores, entry/SL/TP levels, and plain-English reasoning. No black box decisions.",
    icon: Brain,
    iconColor: "#3D8EFF",
    iconBg: "rgba(61, 142, 255, 0.1)",
  },
  {
    step: "03 // Execution",
    title: "Trade Engine",
    description:
      "8-check risk validation pipeline. Position sizing based on account equity and pip value. Orders fire to OANDA with fill verification and automatic SL/TP placement.",
    icon: Zap,
    iconColor: "#FFB347",
    iconBg: "rgba(255, 179, 71, 0.1)",
  },
];

// Visual component for Card 1: Spinning concentric circles
function IngestionVisual({ active }: { active: boolean }) {
  return (
    <div className="relative w-full h-full flex items-center justify-center">
      {[140, 100, 60].map((size, i) => (
        <div
          key={i}
          className="absolute rounded-full border"
          style={{
            width: size,
            height: size,
            borderColor: `rgba(0, 232, 157, ${0.15 - i * 0.03})`,
            animation: active ? `spin ${8 + i * 4}s linear infinite${i % 2 === 1 ? " reverse" : ""}` : "none",
          }}
        >
          {/* Data points on the circle */}
          {Array.from({ length: 4 + i }).map((_, j) => {
            const angle = (j / (4 + i)) * Math.PI * 2;
            const x = Math.cos(angle) * (size / 2);
            const y = Math.sin(angle) * (size / 2);
            return (
              <div
                key={j}
                className="absolute w-1.5 h-1.5 rounded-full"
                style={{
                  backgroundColor: "#00C896",
                  opacity: 0.4 + (j % 3) * 0.2,
                  left: `calc(50% + ${x}px - 3px)`,
                  top: `calc(50% + ${y}px - 3px)`,
                }}
              />
            );
          })}
        </div>
      ))}
      {/* Center dot */}
      <div
        className="w-3 h-3 rounded-full"
        style={{
          backgroundColor: "#00C896",
          boxShadow: "0 0 15px rgba(0, 232, 157, 0.4)",
        }}
      />
    </div>
  );
}

// Visual component for Card 2: Processing nodes
function AnalysisVisual({ active }: { active: boolean }) {
  const nodes = ["Fetch", "Parse", "Score", "Signal"];
  return (
    <div className="flex flex-col gap-3 w-full px-4">
      {nodes.map((node, i) => (
        <div
          key={node}
          className="flex items-center gap-3 transition-all duration-500"
          style={{
            opacity: active ? 1 : 0.3,
            transform: active ? "translateX(0)" : "translateX(10px)",
            transitionDelay: active ? `${i * 150}ms` : "0ms",
          }}
        >
          {/* Pulse dot */}
          <div
            className="w-2 h-2 rounded-full flex-shrink-0"
            style={{
              backgroundColor: "#3D8EFF",
              boxShadow: active ? "0 0 8px rgba(61, 142, 255, 0.5)" : "none",
              animation: active ? `pulse 2s ease-in-out ${i * 0.3}s infinite` : "none",
            }}
          />
          {/* Node label */}
          <div
            className="flex-1 rounded-lg px-3 py-2 font-mono text-xs"
            style={{
              backgroundColor: "rgba(61, 142, 255, 0.06)",
              color: "#3D8EFF",
              border: "1px solid rgba(61, 142, 255, 0.1)",
            }}
          >
            {node}
          </div>
          {/* Connector line */}
          {i < nodes.length - 1 && (
            <div
              className="absolute left-[19px] w-px h-3"
              style={{
                backgroundColor: "rgba(61, 142, 255, 0.15)",
                top: `calc(${i * 44 + 36}px)`,
              }}
            />
          )}
        </div>
      ))}
      {/* Scan line */}
      {active && (
        <div
          className="absolute inset-x-0 h-px"
          style={{
            background: "linear-gradient(90deg, transparent, rgba(61, 142, 255, 0.3), transparent)",
            animation: "scanLine 2s ease-in-out infinite",
          }}
        />
      )}
    </div>
  );
}

// Visual component for Card 3: Terminal output
function ExecutionVisual({ active }: { active: boolean }) {
  const lines = [
    { text: "[INIT] Risk engine ready", color: "#525252", delay: 0 },
    { text: "[PASS] Correlation check", color: "#00C896", delay: 200 },
    { text: "[PASS] Drawdown limit", color: "#00C896", delay: 400 },
    { text: "[PASS] Calendar guard", color: "#00C896", delay: 600 },
    { text: "[EXEC] BUY EUR/USD @ 1.08430", color: "#FFB347", delay: 800 },
    { text: "[FILL] Verified 1,200 units", color: "#00C896", delay: 1000 },
  ];

  return (
    <div
      className="w-full rounded-xl p-4 font-mono text-xs leading-relaxed"
      style={{
        backgroundColor: "rgba(0, 0, 0, 0.3)",
        border: "1px solid rgba(255, 255, 255, 0.04)",
      }}
    >
      {lines.map((line, i) => (
        <div
          key={i}
          className="transition-all duration-300"
          style={{
            opacity: active ? 1 : 0,
            transform: active ? "translateY(0)" : "translateY(5px)",
            transitionDelay: active ? `${line.delay}ms` : "0ms",
            color: line.color,
          }}
        >
          {line.text}
        </div>
      ))}
    </div>
  );
}

const VISUALS = [IngestionVisual, AnalysisVisual, ExecutionVisual];

export default function StackedCards() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [activeCard, setActiveCard] = useState(0);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const rect = container.getBoundingClientRect();
      const containerTop = rect.top;
      const containerHeight = rect.height;
      const viewportHeight = window.innerHeight;

      // Calculate scroll progress through this container
      const scrolled = viewportHeight - containerTop;
      const totalScrollable = containerHeight;
      const progress = Math.max(0, Math.min(1, scrolled / totalScrollable));

      // Map to card index (3 cards, each gets ~1/3 of the scroll)
      const cardIndex = Math.min(2, Math.floor(progress * 3));
      setActiveCard(cardIndex);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();

    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div ref={containerRef} style={{ height: "250vh" }}>
      {/* Section header */}
      <div className="sticky top-24 z-10 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="mb-12">
            <p
              className="font-mono text-xs uppercase tracking-widest mb-3"
              style={{ color: "#00C896" }}
            >
              How It Works
            </p>
            <h2
              className="font-display text-3xl md:text-4xl font-bold"
              style={{ color: "#FFFFFF" }}
            >
              The Lumitrade Method
            </h2>
          </div>

          {/* Card stack */}
          <div className="relative" style={{ minHeight: 400 }}>
            {CARDS.map((card, i) => {
              const Visual = VISUALS[i];
              const isActive = i === activeCard;
              const isPast = i < activeCard;

              return (
                <div
                  key={card.step}
                  className="absolute inset-0 transition-all duration-700 ease-out"
                  style={{
                    opacity: isActive ? 1 : isPast ? 0 : 0.3,
                    transform: isActive
                      ? "translateY(0) scale(1)"
                      : isPast
                      ? "translateY(-30px) scale(0.95)"
                      : `translateY(${(i - activeCard) * 20}px) scale(${1 - (i - activeCard) * 0.02})`,
                    zIndex: isActive ? 10 : isPast ? i : 5 - i,
                    pointerEvents: isActive ? "auto" : "none",
                  }}
                >
                  <div
                    className="rounded-3xl p-8 md:p-10 border"
                    style={{
                      backgroundColor: "#0E0F12",
                      borderColor: "rgba(255, 255, 255, 0.06)",
                      boxShadow: isActive
                        ? `0 25px 50px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.03)`
                        : "none",
                    }}
                  >
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-12 items-center">
                      {/* Left: text content */}
                      <div>
                        <p
                          className="font-mono text-xs uppercase tracking-widest mb-4"
                          style={{ color: card.iconColor, opacity: 0.7 }}
                        >
                          {card.step}
                        </p>
                        <div className="flex items-center gap-3 mb-4">
                          <div
                            className="w-10 h-10 rounded-xl flex items-center justify-center"
                            style={{ backgroundColor: card.iconBg }}
                          >
                            <card.icon size={20} style={{ color: card.iconColor }} />
                          </div>
                          <h3
                            className="font-display text-2xl font-bold"
                            style={{ color: "#FFFFFF" }}
                          >
                            {card.title}
                          </h3>
                        </div>
                        <p
                          className="text-base leading-relaxed"
                          style={{ color: "#A1A1A1" }}
                        >
                          {card.description}
                        </p>

                        {/* Step indicators */}
                        <div className="flex items-center gap-2 mt-8">
                          {CARDS.map((_, j) => (
                            <div
                              key={j}
                              className="h-1 rounded-full transition-all duration-500"
                              style={{
                                width: j === activeCard ? 32 : 8,
                                backgroundColor:
                                  j === activeCard
                                    ? card.iconColor
                                    : "rgba(255, 255, 255, 0.1)",
                              }}
                            />
                          ))}
                        </div>
                      </div>

                      {/* Right: visual */}
                      <div
                        className="relative flex items-center justify-center rounded-2xl overflow-hidden"
                        style={{
                          minHeight: 240,
                          backgroundColor: "rgba(0, 0, 0, 0.2)",
                          border: "1px solid rgba(255, 255, 255, 0.03)",
                        }}
                      >
                        <Visual active={isActive} />
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
