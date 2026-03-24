"use client";

import { useEffect, useState, useCallback } from "react";

interface LoadingScreenProps {
  onComplete: () => void;
}

export default function LoadingScreen({ onComplete }: LoadingScreenProps) {
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(true);

  const handleComplete = useCallback(() => {
    setVisible(false);
    const timeout = setTimeout(() => {
      onComplete();
    }, 600);
    return () => clearTimeout(timeout);
  }, [onComplete]);

  useEffect(() => {
    let current = 0;
    const interval = setInterval(() => {
      // Non-linear acceleration: starts slow, speeds up
      const increment = current < 30 ? 2 : current < 70 ? 4 : current < 90 ? 3 : 1;
      current = Math.min(current + increment, 100);
      setProgress(current);

      if (current >= 100) {
        clearInterval(interval);
        setTimeout(() => {
          handleComplete();
        }, 300);
      }
    }, 30);

    return () => clearInterval(interval);
  }, [handleComplete]);

  return (
    <div
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center"
      style={{
        backgroundColor: "#0D1B2A",
        opacity: visible ? 1 : 0,
        pointerEvents: visible ? "auto" : "none",
        transition: "opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1)",
      }}
    >
      {/* Logo dot */}
      <div
        className="w-3 h-3 rounded-full mb-8"
        style={{
          backgroundColor: "#00C896",
          boxShadow: "0 0 20px rgba(0, 232, 157, 0.4)",
        }}
      />

      {/* Status text */}
      <p
        className="font-mono text-xs tracking-widest uppercase mb-6"
        style={{ color: "#525252" }}
      >
        Initializing Trading Engine
      </p>

      {/* Progress bar container */}
      <div
        className="relative overflow-hidden rounded-full"
        style={{
          width: 200,
          height: 2,
          backgroundColor: "rgba(255, 255, 255, 0.06)",
        }}
      >
        {/* Progress fill */}
        <div
          className="absolute top-0 left-0 h-full rounded-full"
          style={{
            width: `${progress}%`,
            backgroundColor: "#00C896",
            boxShadow: "0 0 8px rgba(0, 232, 157, 0.5)",
            transition: "width 0.05s linear",
          }}
        />
      </div>

      {/* Percentage */}
      <p
        className="font-mono text-xs mt-4 tabular-nums"
        style={{ color: "#525252" }}
      >
        {progress}%
      </p>
    </div>
  );
}
