"use client";

import { useEffect, useRef, useState } from "react";
import { Activity, Cpu, ArrowRightLeft } from "lucide-react";

export default function FeatureBeams() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
        }
      },
      { threshold: 0.3 }
    );

    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={containerRef} className="max-w-5xl mx-auto px-6">
      {/* Section header */}
      <div className="mb-16">
        <p
          className="font-mono text-xs uppercase tracking-widest mb-3"
          style={{ color: "#00C896" }}
        >
          Architecture
        </p>
        <h2
          className="font-display text-3xl md:text-4xl font-bold mb-4"
          style={{ color: "#FFFFFF" }}
        >
          Unified Signal Pipeline
        </h2>
        <p className="text-lg max-w-xl" style={{ color: "#A1A1A1" }}>
          From raw market data to executed trade. One continuous flow, fully automated.
        </p>
      </div>

      {/* Beam visualization */}
      <div className="relative" style={{ minHeight: 320 }}>
        {/* SVG beams (desktop) */}
        <svg
          className="absolute inset-0 w-full h-full hidden md:block"
          viewBox="0 0 800 320"
          fill="none"
          preserveAspectRatio="xMidYMid meet"
          style={{ overflow: "visible" }}
        >
          <defs>
            <linearGradient id="beam-gradient-1" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#00C896" stopOpacity="0.8" />
              <stop offset="50%" stopColor="#00C896" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#3D8EFF" stopOpacity="0.8" />
            </linearGradient>
            <linearGradient id="beam-gradient-2" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#00C896" stopOpacity="0.8" />
              <stop offset="50%" stopColor="#00C896" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#8B5CF6" stopOpacity="0.8" />
            </linearGradient>
            <filter id="glow">
              <feGaussianBlur stdDeviation="3" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Base paths (subtle) */}
          <path
            d="M 200 160 C 350 160, 450 100, 600 100"
            stroke="rgba(255,255,255,0.04)"
            strokeWidth="2"
            fill="none"
          />
          <path
            d="M 200 160 C 350 160, 450 220, 600 220"
            stroke="rgba(255,255,255,0.04)"
            strokeWidth="2"
            fill="none"
          />

          {/* Animated beam 1 (to AI Signal) */}
          <path
            d="M 200 160 C 350 160, 450 100, 600 100"
            stroke="url(#beam-gradient-1)"
            strokeWidth="2"
            fill="none"
            filter="url(#glow)"
            className={isVisible ? "beam-animate-1" : ""}
            style={{
              strokeDasharray: 400,
              strokeDashoffset: isVisible ? 0 : 400,
            }}
          />

          {/* Animated beam 2 (to OANDA Order) */}
          <path
            d="M 200 160 C 350 160, 450 220, 600 220"
            stroke="url(#beam-gradient-2)"
            strokeWidth="2"
            fill="none"
            filter="url(#glow)"
            className={isVisible ? "beam-animate-2" : ""}
            style={{
              strokeDasharray: 400,
              strokeDashoffset: isVisible ? 0 : 400,
            }}
          />

          {/* Animated dots traveling along paths */}
          {isVisible && (
            <>
              <circle r="3" fill="#00C896" filter="url(#glow)">
                <animateMotion
                  dur="3s"
                  repeatCount="indefinite"
                  path="M 200 160 C 350 160, 450 100, 600 100"
                />
              </circle>
              <circle r="3" fill="#8B5CF6" filter="url(#glow)">
                <animateMotion
                  dur="3.5s"
                  repeatCount="indefinite"
                  path="M 200 160 C 350 160, 450 220, 600 220"
                />
              </circle>
            </>
          )}
        </svg>

        {/* Cards */}
        <div className="relative z-10 flex flex-col md:flex-row items-center md:items-stretch justify-between gap-8 md:gap-0">
          {/* Source node (left) */}
          <div
            className="w-full md:w-[220px] transition-all duration-700"
            style={{
              opacity: isVisible ? 1 : 0,
              transform: isVisible ? "translateX(0)" : "translateX(-20px)",
            }}
          >
            <div
              className="rounded-2xl p-5 border"
              style={{
                backgroundColor: "#0E0F12",
                borderColor: "rgba(0, 232, 157, 0.15)",
                boxShadow: "0 0 30px rgba(0, 232, 157, 0.05)",
              }}
            >
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
                style={{ backgroundColor: "rgba(0, 232, 157, 0.1)" }}
              >
                <Activity size={20} style={{ color: "#00C896" }} />
              </div>
              <p className="font-display font-semibold text-sm mb-1" style={{ color: "#FFFFFF" }}>
                Price Stream
              </p>
              <p className="text-xs" style={{ color: "#525252" }}>
                OANDA v20 API
              </p>
              {/* Skeleton bars */}
              <div className="mt-4 space-y-2">
                <div className="h-1.5 rounded-full w-full" style={{ backgroundColor: "rgba(0, 232, 157, 0.1)" }} />
                <div className="h-1.5 rounded-full w-3/4" style={{ backgroundColor: "rgba(0, 232, 157, 0.06)" }} />
                <div className="h-1.5 rounded-full w-1/2" style={{ backgroundColor: "rgba(0, 232, 157, 0.04)" }} />
              </div>
            </div>
          </div>

          {/* Mobile arrows */}
          <div className="md:hidden flex flex-col items-center gap-2">
            <div className="w-px h-8" style={{ backgroundColor: "rgba(0, 232, 157, 0.2)" }} />
            <ArrowRightLeft size={16} style={{ color: "#00C896", opacity: 0.4 }} />
            <div className="w-px h-8" style={{ backgroundColor: "rgba(0, 232, 157, 0.2)" }} />
          </div>

          {/* Output nodes (right) */}
          <div
            className="w-full md:w-[220px] flex flex-col gap-5 transition-all duration-700"
            style={{
              opacity: isVisible ? 1 : 0,
              transform: isVisible ? "translateX(0)" : "translateX(20px)",
              transitionDelay: "0.3s",
            }}
          >
            {/* AI Signal node */}
            <div
              className="rounded-2xl p-5 border"
              style={{
                backgroundColor: "#0E0F12",
                borderColor: "rgba(61, 142, 255, 0.15)",
                boxShadow: "0 0 30px rgba(61, 142, 255, 0.05)",
              }}
            >
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
                style={{ backgroundColor: "rgba(61, 142, 255, 0.1)" }}
              >
                <Cpu size={20} style={{ color: "#3D8EFF" }} />
              </div>
              <p className="font-display font-semibold text-sm mb-1" style={{ color: "#FFFFFF" }}>
                AI Signal
              </p>
              <p className="text-xs" style={{ color: "#525252" }}>
                Claude 3.5 Sonnet
              </p>
              {/* Skeleton bars */}
              <div className="mt-4 space-y-2">
                <div className="h-1.5 rounded-full w-full" style={{ backgroundColor: "rgba(61, 142, 255, 0.1)" }} />
                <div className="h-1.5 rounded-full w-2/3" style={{ backgroundColor: "rgba(61, 142, 255, 0.06)" }} />
              </div>
            </div>

            {/* OANDA Order node */}
            <div
              className="rounded-2xl p-5 border"
              style={{
                backgroundColor: "#0E0F12",
                borderColor: "rgba(139, 92, 246, 0.15)",
                boxShadow: "0 0 30px rgba(139, 92, 246, 0.05)",
              }}
            >
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
                style={{ backgroundColor: "rgba(139, 92, 246, 0.1)" }}
              >
                <ArrowRightLeft size={20} style={{ color: "#8B5CF6" }} />
              </div>
              <p className="font-display font-semibold text-sm mb-1" style={{ color: "#FFFFFF" }}>
                OANDA Order
              </p>
              <p className="text-xs" style={{ color: "#525252" }}>
                Fill verified
              </p>
              {/* Skeleton bars */}
              <div className="mt-4 space-y-2">
                <div className="h-1.5 rounded-full w-full" style={{ backgroundColor: "rgba(139, 92, 246, 0.1)" }} />
                <div className="h-1.5 rounded-full w-4/5" style={{ backgroundColor: "rgba(139, 92, 246, 0.06)" }} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
