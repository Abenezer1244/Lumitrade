"use client";

import { useRef, useState, useCallback } from "react";
import { motion, useReducedMotion } from "motion/react";
import type { LucideIcon } from "lucide-react";

interface FeatureCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
  accentColor: string;
  index: number;
}

export default function FeatureCard({
  icon: Icon,
  title,
  description,
  accentColor,
  index,
}: FeatureCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);
  const prefersReducedMotion = useReducedMotion();

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!cardRef.current) return;
      const rect = cardRef.current.getBoundingClientRect();
      setMousePos({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      });
    },
    []
  );

  return (
    <motion.div
      ref={cardRef}
      initial={prefersReducedMotion ? { opacity: 1 } : { opacity: 0, y: 24, filter: "blur(8px)" }}
      whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{
        type: "spring",
        bounce: 0.2,
        duration: 0.8,
        delay: index * 0.1,
      }}
      whileHover={prefersReducedMotion ? {} : { y: -4 }}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className="glass relative overflow-hidden group cursor-default"
      style={{
        borderColor: isHovered ? "var(--color-border-accent)" : undefined,
        transition: "border-color 0.2s ease",
      }}
    >
      {/* Mouse-following radial glow overlay */}
      <div
        className="pointer-events-none absolute inset-0 opacity-0 group-hover:opacity-100"
        style={{
          transition: "opacity 0.3s ease",
          background: isHovered
            ? `radial-gradient(320px circle at ${mousePos.x}px ${mousePos.y}px, var(--color-brand-dim), transparent 60%)`
            : "none",
        }}
      />

      {/* Corner decorators — visible on hover */}
      {isHovered && (
        <>
          <span
            className="absolute top-2 left-2 w-2 h-2 rounded-[1px] opacity-50"
            style={{ backgroundColor: accentColor }}
          />
          <span
            className="absolute top-2 right-2 w-2 h-2 rounded-[1px] opacity-50"
            style={{ backgroundColor: accentColor }}
          />
          <span
            className="absolute bottom-2 left-2 w-2 h-2 rounded-[1px] opacity-50"
            style={{ backgroundColor: accentColor }}
          />
          <span
            className="absolute bottom-2 right-2 w-2 h-2 rounded-[1px] opacity-50"
            style={{ backgroundColor: accentColor }}
          />
        </>
      )}

      <div className="relative z-10 p-6">
        {/* Icon container */}
        <div
          className="w-11 h-11 rounded-lg flex items-center justify-center mb-5"
          style={{
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-bg-primary)",
          }}
        >
          <Icon size={20} style={{ color: accentColor }} />
        </div>

        <h3
          className="font-display text-lg font-semibold mb-2"
          style={{ color: "var(--color-text-primary)" }}
        >
          {title}
        </h3>
        <p
          className="text-sm leading-relaxed"
          style={{ color: "var(--color-text-secondary)" }}
        >
          {description}
        </p>
      </div>
    </motion.div>
  );
}
