"use client";

import { useEffect, useRef, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Music, ArrowRight, ShieldCheck, Sparkles, CheckCircle2, AlertCircle } from "lucide-react";
import { Reveal } from "@/components/MotionWrap";

const CODE_LEN = 6;
const PIN_CHAR_OK = /^[2-9A-HJ-NP-Z]$/i;

function SpotifyAuthContent() {
  const searchParams = useSearchParams();
  const initialCode = (searchParams.get("code") || "").trim().toUpperCase().slice(0, CODE_LEN);
  const errorMsg = searchParams.get("error");

  const [cells, setCells] = useState<string[]>(() => {
    if (initialCode.length === CODE_LEN) {
      return initialCode.split("");
    }
    return Array(CODE_LEN).fill("");
  });

  const [error, setError] = useState(errorMsg || "");
  const refs = useRef<Array<HTMLInputElement | null>>([]);
  refs.current = refs.current.slice(0, CODE_LEN);

  const code = cells.join("").toUpperCase();
  const isComplete = code.length === CODE_LEN;

  useEffect(() => {
    if (initialCode.length === CODE_LEN) {
      setCells(initialCode.split(""));
    } else {
      refs.current[0]?.focus();
    }
  }, [initialCode]);

  function setCell(i: number, raw: string) {
    const v = (raw || "").toUpperCase();

    // Multicharacter paste
    if (v.length > 1) {
      const parts = v.replace(/[^2-9A-HJ-NP-Z]/gi, "").split("").slice(0, CODE_LEN - i);
      const next = [...cells];
      parts.forEach((c, k) => {
        next[i + k] = c;
      });
      setCells(next);
      const last = Math.min(CODE_LEN - 1, i + parts.length);
      refs.current[last]?.focus();
      setError("");
      return;
    }

    if (v && !PIN_CHAR_OK.test(v)) return;

    const next = [...cells];
    next[i] = v;
    setCells(next);
    setError("");

    if (v && i < CODE_LEN - 1) {
      refs.current[i + 1]?.focus();
    }
  }

  function handleKeyDown(i: number, e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace" && !cells[i] && i > 0) {
      refs.current[i - 1]?.focus();
    }
  }

  function handleStartOAuth() {
    if (!isComplete) {
      setError("Please enter the 6-character PIN shown on your badge.");
      return;
    }
    window.location.href = `/api/spotify/login?code=${encodeURIComponent(code)}`;
  }

  return (
    <div className="relative min-h-[calc(100vh-5rem)] flex items-center justify-center px-4 py-16">
      {/* Background ambient lighting */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-1/4 -translate-x-1/2 -translate-y-1/2 w-[520px] h-[520px] rounded-full bg-[#1DB954]/10 blur-[130px]" />
        <div className="absolute right-1/4 bottom-1/4 w-[380px] h-[380px] rounded-full bg-primary/10 blur-[110px]" />
      </div>

      <div className="relative w-full max-w-lg">
        <Reveal>
          <div className="card-surface rounded-2xl border border-border bg-card/90 backdrop-blur-xl p-8 sm:p-10 shadow-2xl">
            {/* Header / Brand Icon */}
            <div className="flex items-center justify-between gap-4 mb-8">
              <div className="flex items-center gap-3.5">
                <div className="w-12 h-12 rounded-xl bg-[#1DB954]/15 border border-[#1DB954]/30 flex items-center justify-center text-[#1DB954] shadow-inner">
                  <Music className="w-6 h-6" />
                </div>
                <div>
                  <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-text">
                    Link Spotify
                  </h1>
                  <p className="text-xs text-text-dim mt-0.5">
                    Connect your account to your Oreo Badge
                  </p>
                </div>
              </div>

              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-bg-raised border border-border text-text-dim">
                <Sparkles className="w-3 h-3 text-[#1DB954]" />
                Music App
              </span>
            </div>

            {/* Error Banner */}
            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  className="mb-6 p-3.5 rounded-xl bg-primary/10 border border-primary/30 flex items-start gap-2.5 text-xs text-primary"
                >
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <p>{error}</p>
                </motion.div>
              )}
            </AnimatePresence>

            {/* PIN Entry Area */}
            <div className="mb-6">
              <div className="flex items-center justify-between mb-3">
                <label className="text-xs font-semibold uppercase tracking-wider text-muted">
                  Badge Screen PIN
                </label>
                {initialCode && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium text-teal">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Auto-filled from QR
                  </span>
                )}
              </div>

              <div className="grid grid-cols-6 gap-2 sm:gap-3">
                {cells.map((val, i) => (
                  <input
                    key={i}
                    ref={(el) => {
                      refs.current[i] = el;
                    }}
                    type="text"
                    maxLength={2}
                    value={val}
                    onChange={(e) => setCell(i, e.target.value)}
                    onKeyDown={(e) => handleKeyDown(i, e)}
                    className={`h-14 sm:h-16 text-center text-xl sm:text-2xl font-mono font-bold rounded-xl border bg-bg-raised text-text transition-all outline-none ${
                      val
                        ? "border-[#1DB954] shadow-[0_0_12px_rgba(29,185,84,0.25)]"
                        : "border-border hover:border-border/80 focus:border-primary"
                    }`}
                  />
                ))}
              </div>
              <p className="text-[11px] text-muted mt-2.5 text-center">
                Look at your badge screen under the QR code for your 6-character code.
              </p>
            </div>

            {/* Action CTA Button */}
            <motion.button
              whileHover={{ scale: 1.015 }}
              whileTap={{ scale: 0.985 }}
              onClick={handleStartOAuth}
              disabled={!isComplete}
              className={`w-full py-4 px-6 rounded-xl font-semibold flex items-center justify-center gap-2.5 transition-all shadow-lg text-sm sm:text-base ${
                isComplete
                  ? "bg-[#1DB954] hover:bg-[#1ed760] text-black shadow-[#1DB954]/25 cursor-pointer font-bold"
                  : "bg-bg-raised text-muted border border-border cursor-not-allowed"
              }`}
            >
              <svg className="w-5 h-5 fill-current" viewBox="0 0 24 24">
                <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z" />
              </svg>
              <span>Log in with Spotify</span>
              <ArrowRight className="w-4 h-4 ml-1" />
            </motion.button>

            {/* Privacy & Zero-Config Guarantee Footer */}
            <div className="mt-6 pt-5 border-t border-border/60 flex items-center justify-between text-[11px] text-muted">
              <span className="flex items-center gap-1.5 text-teal">
                <ShieldCheck className="w-3.5 h-3.5" />
                Zero credentials stored on cloud
              </span>
              <span className="text-text-dim font-mono">1-Time Token Relay</span>
            </div>
          </div>
        </Reveal>
      </div>
    </div>
  );
}

export default function SpotifyPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center">
          <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
        </div>
      }
    >
      <SpotifyAuthContent />
    </Suspense>
  );
}
