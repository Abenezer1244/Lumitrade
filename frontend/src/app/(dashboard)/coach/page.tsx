"use client";

import { useState, useRef, useEffect, useCallback, type FormEvent, type KeyboardEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageCircle, Send, Bot, User } from "lucide-react";

/* ── Types ────────────────────────────────────────────────────── */

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

/* ── Constants ────────────────────────────────────────────────── */

const SUGGESTED_QUESTIONS = [
  "Why did my last trade lose?",
  "Which pair performs best?",
  "Should I change my risk settings?",
  "What patterns do you see in my wins?",
  "How is my confidence score correlated with outcomes?",
  "What exit reasons are costing me the most?",
];

/* ── Component ────────────────────────────────────────────────── */

export default function CoachPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  /* Auto-scroll to bottom on new message */
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  /* Auto-resize textarea */
  const handleInputChange = (value: string) => {
    setInput(value);
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 120)}px`;
    }
  };

  /* Send message */
  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isLoading) return;

      setError(null);
      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: trimmed,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      if (inputRef.current) {
        inputRef.current.style.height = "auto";
      }
      setIsLoading(true);

      try {
        const res = await fetch("/api/coach", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: trimmed }),
        });

        const data = (await res.json()) as { response?: string; error?: string };

        if (!res.ok || data.error) {
          setError(data.error ?? "Something went wrong. Please try again.");
          setIsLoading(false);
          return;
        }

        const assistantMsg: ChatMessage = {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: data.response ?? "No response.",
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } catch {
        setError("Network error. Please check your connection.");
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading]
  );

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    void sendMessage(input);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void sendMessage(input);
    }
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)]">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <div
          className="flex items-center justify-center w-10 h-10 rounded-lg"
          style={{ backgroundColor: "var(--color-accent)", opacity: 0.15 }}
        >
          <Bot size={20} style={{ color: "var(--color-accent)" }} />
        </div>
        <div>
          <h1
            className="text-xl font-display font-semibold"
            style={{ color: "var(--color-text-primary)" }}
          >
            AI Trading Coach
          </h1>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Ask about your trades, patterns, and performance
          </p>
        </div>
      </div>

      {/* Chat Area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto pr-2"
        style={{ scrollBehavior: "smooth" }}
      >
        {isEmpty ? (
          <EmptyState onSelect={(q) => void sendMessage(q)} />
        ) : (
          <div className="space-y-4 pb-4">
            <AnimatePresence initial={false}>
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
            </AnimatePresence>

            {/* Loading indicator */}
            {isLoading && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-start gap-3"
              >
                <div
                  className="flex items-center justify-center w-8 h-8 rounded-lg flex-shrink-0"
                  style={{ backgroundColor: "var(--color-bg-elevated)" }}
                >
                  <Bot size={16} style={{ color: "var(--color-accent)" }} />
                </div>
                <div
                  className="glass px-4 py-3 rounded-xl max-w-[75%]"
                  style={{ borderColor: "var(--color-border)" }}
                >
                  <TypingIndicator />
                </div>
              </motion.div>
            )}
          </div>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div
          className="mx-0 mb-2 px-4 py-2 rounded-lg text-sm"
          style={{
            backgroundColor: "var(--color-loss-dim, rgba(255,77,106,0.1))",
            color: "var(--color-loss)",
            border: "1px solid var(--color-loss)",
          }}
        >
          {error}
        </div>
      )}

      {/* Input Area */}
      <form onSubmit={handleSubmit} className="flex-shrink-0 pt-3">
        <div
          className="glass flex items-end gap-2 p-3 rounded-xl"
          style={{ borderColor: "var(--color-border)" }}
        >
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => handleInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your trading performance..."
            rows={1}
            disabled={isLoading}
            className="flex-1 bg-transparent resize-none outline-none text-sm font-sans"
            style={{
              color: "var(--color-text-primary)",
              minHeight: "36px",
              maxHeight: "120px",
            }}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="flex items-center justify-center w-9 h-9 rounded-lg transition-all duration-150 flex-shrink-0 disabled:opacity-30"
            style={{
              backgroundColor: "var(--color-accent)",
              color: "#fff",
            }}
            aria-label="Send message"
          >
            <Send size={16} />
          </button>
        </div>
        <p
          className="text-xs mt-2 text-center"
          style={{ color: "var(--color-text-tertiary, #4A5E80)" }}
        >
          AI coach analyzes your real trade history. Shift+Enter for new line.
        </p>
      </form>
    </div>
  );
}

/* ── Sub-components ───────────────────────────────────────────── */

function EmptyState({ onSelect }: { onSelect: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <div
        className="flex items-center justify-center w-16 h-16 rounded-2xl mb-6"
        style={{
          backgroundColor: "var(--color-bg-elevated)",
          border: "1px solid var(--color-border)",
        }}
      >
        <MessageCircle size={28} style={{ color: "var(--color-accent)" }} />
      </div>
      <h2
        className="text-lg font-display font-semibold mb-2"
        style={{ color: "var(--color-text-primary)" }}
      >
        Your AI Trading Coach
      </h2>
      <p
        className="text-sm mb-8 text-center max-w-md"
        style={{ color: "var(--color-text-secondary)" }}
      >
        Ask questions about your trading performance, patterns, and get
        data-driven recommendations based on your real trade history.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
        {SUGGESTED_QUESTIONS.map((q) => (
          <button
            key={q}
            onClick={() => onSelect(q)}
            className="glass px-4 py-3 rounded-xl text-left text-sm transition-all duration-150 hover:scale-[1.02]"
            style={{
              color: "var(--color-text-secondary)",
              borderColor: "var(--color-border)",
            }}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={`flex items-start gap-3 ${isUser ? "flex-row-reverse" : ""}`}
    >
      {/* Avatar */}
      <div
        className="flex items-center justify-center w-8 h-8 rounded-lg flex-shrink-0"
        style={{
          backgroundColor: isUser
            ? "var(--color-accent)"
            : "var(--color-bg-elevated)",
        }}
      >
        {isUser ? (
          <User size={16} style={{ color: "#fff" }} />
        ) : (
          <Bot size={16} style={{ color: "var(--color-accent)" }} />
        )}
      </div>

      {/* Bubble */}
      <div
        className={`px-4 py-3 rounded-xl max-w-[75%] text-sm leading-relaxed ${
          isUser ? "" : "glass"
        }`}
        style={
          isUser
            ? {
                backgroundColor: "var(--color-accent)",
                color: "#fff",
              }
            : {
                color: "var(--color-text-primary)",
                borderColor: "var(--color-border)",
              }
        }
      >
        <MessageContent content={message.content} />
      </div>
    </motion.div>
  );
}

function MessageContent({ content }: { content: string }) {
  // Render paragraphs and inline code blocks
  const parts = content.split(/\n\n+/);
  return (
    <div className="space-y-2">
      {parts.map((paragraph, i) => {
        // Check for code blocks
        if (paragraph.startsWith("```")) {
          const code = paragraph.replace(/```\w*\n?/, "").replace(/```$/, "");
          return (
            <pre
              key={i}
              className="font-mono text-xs p-3 rounded-lg overflow-x-auto"
              style={{
                backgroundColor: "var(--color-bg-primary)",
                border: "1px solid var(--color-border)",
              }}
            >
              {code}
            </pre>
          );
        }

        // Render lines within paragraph preserving single newlines
        const lines = paragraph.split("\n");
        return (
          <p key={i}>
            {lines.map((line, j) => (
              <span key={j}>
                {j > 0 && <br />}
                <InlineFormatted text={line} />
              </span>
            ))}
          </p>
        );
      })}
    </div>
  );
}

function InlineFormatted({ text }: { text: string }) {
  // Bold and inline code
  const segments = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return (
    <>
      {segments.map((seg, i) => {
        if (seg.startsWith("**") && seg.endsWith("**")) {
          return (
            <strong key={i} className="font-semibold">
              {seg.slice(2, -2)}
            </strong>
          );
        }
        if (seg.startsWith("`") && seg.endsWith("`")) {
          return (
            <code
              key={i}
              className="font-mono text-xs px-1.5 py-0.5 rounded"
              style={{
                backgroundColor: "var(--color-bg-elevated)",
                color: "var(--color-accent)",
              }}
            >
              {seg.slice(1, -1)}
            </code>
          );
        }
        return <span key={i}>{seg}</span>;
      })}
    </>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 py-1">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="w-2 h-2 rounded-full"
          style={{ backgroundColor: "var(--color-text-tertiary, #4A5E80)" }}
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{
            duration: 1.2,
            repeat: Infinity,
            delay: i * 0.2,
          }}
        />
      ))}
    </div>
  );
}
