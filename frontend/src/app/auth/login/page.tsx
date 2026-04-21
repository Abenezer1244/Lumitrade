"use client";

import { useState, FormEvent } from "react";
import { createClient } from "@/lib/supabase";
import { Mail } from "lucide-react";
import Link from "next/link";
import LoadingSpinner from "@/components/ui/LoadingSpinner";

type AuthState = "idle" | "loading" | "success" | "error";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [authState, setAuthState] = useState<AuthState>("idle");
  const [errorMessage, setErrorMessage] = useState("");

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!email.trim()) return;

    setAuthState("loading");
    setErrorMessage("");

    try {
      const supabase = createClient();
      const { error } = await supabase.auth.signInWithOtp({
        email: email.trim(),
        options: {
          emailRedirectTo: `${window.location.origin}/auth/callback`,
        },
      });

      if (error) {
        setAuthState("error");
        setErrorMessage(error.message);
        return;
      }

      setAuthState("success");
    } catch {
      setAuthState("error");
      setErrorMessage("An unexpected error occurred. Please try again.");
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4 relative"
      style={{ backgroundColor: "var(--color-bg-primary)" }}
    >
      {/* Brand radial glow — uses brand token so it matches across themes */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(600px circle at 50% 40%, color-mix(in srgb, var(--color-brand) 8%, transparent), transparent 70%)",
        }}
      />

      <div className="glass p-8 w-full max-w-sm relative z-10">
        {/* Logo */}
        <div className="text-center">
          <h1 className="font-mono text-2xl font-bold text-brand tracking-wide">
            LUMITRADE
          </h1>
          <p className="text-sm text-secondary mt-1">
            AI-Powered Forex Trading
          </p>
        </div>

        <div className="border-t border-border my-6" />

        {authState === "success" ? (
          <div className="text-center py-4">
            <Mail size={32} className="text-accent mx-auto mb-3" />
            <p className="text-sm text-primary font-medium">
              Check your email for a login link
            </p>
            <p className="text-xs text-secondary mt-2">
              We sent a magic link to{" "}
              <span className="font-mono text-primary">{email}</span>
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label htmlFor="email" className="text-label text-tertiary mb-1 block">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="trader@example.com"
                required
                autoComplete="email"
                className="glass-elevated px-4 py-3 w-full text-sm text-primary placeholder:text-tertiary focus:outline-none transition-colors"
                style={{ borderColor: "var(--color-border)" }}
              />
            </div>

            {authState === "error" && errorMessage && (
              <p className="text-xs text-loss">{errorMessage}</p>
            )}

            <button
              type="submit"
              disabled={authState === "loading" || !email.trim()}
              className="w-full rounded-lg py-3 text-sm font-bold transition-colors disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              style={{ backgroundColor: "var(--color-brand)", color: "var(--color-bg-primary)" }}
            >
              {authState === "loading" ? (
                <>
                  <LoadingSpinner size="sm" />
                  Sending link...
                </>
              ) : (
                "Sign In"
              )}
            </button>
          </form>
        )}

        <div className="border-t mt-6 pt-4" style={{ borderColor: "var(--color-border)" }}>
          <p className="text-xs text-center" style={{ color: "var(--color-text-tertiary)" }}>
            Don&apos;t have an account?{" "}
            <Link href="/auth/signup" className="font-medium transition-colors hover:underline" style={{ color: "var(--color-brand)" }}>
              Sign up free
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
