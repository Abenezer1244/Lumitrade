"use client";

import { useEffect, useRef, useState } from "react";

interface KaraokeTextProps {
  text: string;
}

export default function KaraokeText({ text }: KaraokeTextProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [isVisible, setIsVisible] = useState(false);

  const words = text.split(" ");

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // IntersectionObserver to toggle scroll listener
    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsVisible(entry.isIntersecting);
      },
      { threshold: 0.1 }
    );

    observer.observe(container);

    return () => {
      observer.disconnect();
    };
  }, []);

  useEffect(() => {
    if (!isVisible) return;

    const container = containerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const rect = container.getBoundingClientRect();
      const viewportHeight = window.innerHeight;

      // Calculate how far through the element we've scrolled
      // Start highlighting when element enters viewport, finish when it's about to leave
      const elementTop = rect.top;
      const elementHeight = rect.height;

      // Progress: 0 when top enters viewport, 1 when bottom exits
      const start = viewportHeight * 0.8;
      const end = -elementHeight * 0.2;
      const progress = Math.max(0, Math.min(1, (start - elementTop) / (start - end)));

      // Map progress to word index
      const wordIndex = Math.floor(progress * words.length) - 1;
      setActiveIndex(wordIndex);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll(); // Initial check

    return () => {
      window.removeEventListener("scroll", handleScroll);
    };
  }, [isVisible, words.length]);

  return (
    <div ref={containerRef} className="max-w-4xl mx-auto py-8">
      <p className="font-display text-3xl md:text-5xl lg:text-6xl font-bold leading-tight tracking-tight">
        {words.map((word, i) => (
          <span
            key={i}
            className="inline-block mr-[0.3em] transition-all duration-300 ease-out"
            style={{
              opacity: i <= activeIndex ? 1 : 0.15,
              color: i <= activeIndex ? "#FFFFFF" : "#525252",
              textShadow: i <= activeIndex ? "0 0 30px rgba(0, 232, 157, 0.15)" : "none",
            }}
          >
            {word}
          </span>
        ))}
      </p>
    </div>
  );
}
