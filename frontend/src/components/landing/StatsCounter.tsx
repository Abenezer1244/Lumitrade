"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion, useInView } from "motion/react";

interface StatItem {
  value: number;
  suffix: string;
  label: string;
}

interface StatsCounterProps {
  stats: StatItem[];
}

function AnimatedNumber({
  target,
  suffix,
  inView,
}: {
  target: number;
  suffix: string;
  inView: boolean;
}) {
  const [current, setCurrent] = useState(0);
  const prefersReducedMotion = useReducedMotion();

  useEffect(() => {
    if (!inView) return;

    if (prefersReducedMotion) {
      setCurrent(target);
      return;
    }

    let startTime: number | null = null;
    const duration = 1600;
    let rafId: number;

    const animate = (timestamp: number) => {
      if (!startTime) startTime = timestamp;
      const elapsed = timestamp - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Ease-out cubic for natural deceleration
      const eased = 1 - Math.pow(1 - progress, 3);
      setCurrent(Math.round(eased * target));

      if (progress < 1) {
        rafId = requestAnimationFrame(animate);
      }
    };

    rafId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafId);
  }, [inView, target, prefersReducedMotion]);

  return (
    <span className="font-mono text-4xl md:text-5xl font-semibold" style={{ color: "var(--color-text-primary)" }}>
      {current}
      <span style={{ color: "var(--color-brand)" }}>{suffix}</span>
    </span>
  );
}

export default function StatsCounter({ stats }: StatsCounterProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(containerRef, { once: true, margin: "-80px" });
  const prefersReducedMotion = useReducedMotion();

  return (
    <div
      ref={containerRef}
      className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-12"
    >
      {stats.map((stat, i) => (
        <motion.div
          key={stat.label}
          initial={prefersReducedMotion ? { opacity: 1 } : { opacity: 0, y: 16 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{
            type: "spring",
            bounce: 0.2,
            duration: 0.7,
            delay: i * 0.1,
          }}
          className="text-center"
        >
          <AnimatedNumber
            target={stat.value}
            suffix={stat.suffix}
            inView={isInView}
          />
          <p
            className="mt-2 text-xs font-medium uppercase tracking-wider"
            style={{ color: "var(--color-text-tertiary)" }}
          >
            {stat.label}
          </p>
        </motion.div>
      ))}
    </div>
  );
}
