"use client";

import { useState, FormEvent } from "react";
import { createClient } from "@/lib/supabase";
import { Mail, ArrowRight } from "lucide-react";
import Link from "next/link";
import LoadingSpinner from "@/components/ui/LoadingSpinner";

type AuthState = "idle" | "loading" | "success" | "error";

export default function SignUpPage() {
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
    } catch (e) {
      console.error("auth signup failed", e);
      setAuthState("error");
      setErrorMessage(e instanceof Error ? e.message : "Authentication failed");
    }
  }

  return (
    <div
      className="min-h-[100dvh] flex items-center justify-center px-4 relative"
      style={{ backgroundColor: "var(--color-bg-primary)" }}
    >
      {/* Emerald radial glow */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(600px circle at 50% 40%, rgba(0,232,157,0.06), transparent 70%)",
        }}
      />

      <div className="glass p-8 w-full max-w-sm relative z-10">
        {/* Logo */}
        <div className="text-center">
          <h1 className="font-mono text-2xl font-bold tracking-wide" style={{ color: "var(--color-brand)" }}>
            LUMITRADE
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--color-text-secondary)" }}>
            Start trading with AI precision
          </p>
        </div>

        <div className="border-t my-6" style={{ borderColor: "var(--color-border)" }} />

        {authState === "success" ? (
          <div className="text-center py-4">
            <Mail size={32} className="mx-auto mb-3" style={{ color: "var(--color-brand)" }} />
            <p className="text-sm font-medium" style={{ color: "var(--color-text-primary)" }}>
              Check your email to get started
            </p>
            <p className="text-xs mt-2" style={{ color: "var(--color-text-secondary)" }}>
              We sent a magic link to{" "}
              <span className="font-mono" style={{ color: "var(--color-text-primary)" }}>{email}</span>
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="signup-email" className="text-label block mb-1" style={{ color: "var(--color-text-tertiary)" }}>
                Email
              </label>
              <input
                id="signup-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="trader@example.com"
                required
                autoComplete="email"
                className="glass-elevated px-4 py-3 w-full text-sm rounded-lg focus:outline-none transition-colors"
                style={{
                  color: "var(--color-text-primary)",
                  borderColor: "var(--color-border)",
                }}
              />
            </div>

            {authState === "error" && errorMessage && (
              <p className="text-xs" style={{ color: "var(--color-loss)" }}>{errorMessage}</p>
            )}

            <button
              type="submit"
              disabled={authState === "loading" || !email.trim()}
              className="w-full rounded-lg py-3 text-sm font-bold transition-colors disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              style={{ backgroundColor: "var(--color-brand)", color: "#0D1B2A" }}
            >
              {authState === "loading" ? (
                <>
                  <LoadingSpinner size="sm" />
                  Creating account...
                </>
              ) : (
                <>
                  Create Free Account
                  <ArrowRight size={14} />
                </>
              )}
            </button>

            <p className="text-xs text-center mt-3" style={{ color: "var(--color-text-tertiary)" }}>
              Free paper trading. No credit card required.
            </p>
          </form>
        )}

        <div className="border-t mt-6 pt-4" style={{ borderColor: "var(--color-border)" }}>
          <p className="text-xs text-center" style={{ color: "var(--color-text-tertiary)" }}>
            Already have an account?{" "}
            <Link href="/auth/login" className="font-medium transition-colors hover:underline" style={{ color: "var(--color-brand)" }}>
              Log in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
