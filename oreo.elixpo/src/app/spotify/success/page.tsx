"use client";

import { useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { CheckCircle2, Sparkles, Radio } from "lucide-react";
import { Reveal } from "@/components/MotionWrap";

function SpotifySuccessContent() {
  const searchParams = useSearchParams();
  const code = searchParams.get("code") || "";

  useEffect(() => {
    // Confetti / celebratory vibrations if available
    if (typeof navigator !== "undefined" && navigator.vibrate) {
      navigator.vibrate([100, 50, 100]);
    }
  }, []);

  return (
    <div className="relative min-h-[calc(100vh-5rem)] flex items-center justify-center px-4 py-16">
      {/* Ambient Spotify green glow */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[580px] h-[580px] rounded-full bg-[#1DB954]/15 blur-[140px]" />
      </div>

      <div className="relative w-full max-w-md">
        <Reveal>
          <div className="card-surface rounded-2xl border border-border bg-card/90 backdrop-blur-xl p-8 sm:p-10 text-center shadow-2xl">
            {/* Animated Icon */}
            <motion.div
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: "spring", stiffness: 300, damping: 20 }}
              className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-[#1DB954]/15 border border-[#1DB954]/40 flex items-center justify-center text-[#1DB954] shadow-lg shadow-[#1DB954]/20"
            >
              <CheckCircle2 className="w-10 h-10" />
            </motion.div>

            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-[#1DB954]/10 border border-[#1DB954]/30 text-[#1DB954] mb-3">
              <Radio className="w-3.5 h-3.5 animate-pulse" />
              Badge Connected
            </span>

            <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-text mb-2">
              Spotify Linked!
            </h1>
            <p className="text-sm text-text-dim leading-relaxed max-w-xs mx-auto mb-6">
              Your Spotify account has been authorized. Look at your Oreo Badge screen!
            </p>

            {code && (
              <div className="p-3 rounded-xl bg-bg-raised border border-border mb-6 flex items-center justify-center gap-2">
                <span className="text-xs text-muted uppercase font-semibold">Session PIN:</span>
                <span className="font-mono text-sm font-bold text-text tracking-widest">{code}</span>
              </div>
            )}

            <div className="p-4 rounded-xl bg-[#1DB954]/10 border border-[#1DB954]/20 text-xs text-text-dim text-left">
              <p className="flex items-center gap-1.5 font-medium text-[#1DB954] mb-1">
                <Sparkles className="w-4 h-4 shrink-0" />
                Live Music Sync Ready
              </p>
              <p className="leading-relaxed">Play any song on your phone or desktop Spotify to see live album art, track details, and controls on your badge.</p>
            </div>
          </div>
        </Reveal>
      </div>
    </div>
  );
}

export default function SpotifySuccessPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center">
          <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
        </div>
      }
    >
      <SpotifySuccessContent />
    </Suspense>
  );
}
