import crypto from "crypto";

/**
 * Temporary PIN Session Store for Oreo Badge Spotify Auth.
 *
 * Supports in-memory storage with automatic TTL expiry (10 minutes)
 * for bridging the OAuth handshake between web browsers and hardware badges.
 */

export interface SpotifySession {
  code: string;
  status: "pending" | "authorized" | "expired" | "consumed";
  createdAt: number;
  consumedAt?: number;
  accessToken?: string;
  refreshToken?: string;
  clientId?: string;
}

const SESSION_TTL_MS = 10 * 60 * 1000; // 10 minutes

// Maintain a global singleton map to survive Next.js module reloads in development/serverless
declare global {

  var __spotifySessions: Map<string, SpotifySession> | undefined;
}

const sessions = globalThis.__spotifySessions || new Map<string, SpotifySession>();
globalThis.__spotifySessions = sessions;

// Characters for clean, readable 6-character PIN (no ambiguous 0/O, 1/I)
const PIN_CHARS = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ";

export function normalizePin(code: string): string {
  return (code || "")
    .replace(/[^2-9a-hj-np-z]/gi, "")
    .trim()
    .toUpperCase();
}

export function generatePin(len = 6): string {
  let res = "";
  for (let i = 0; i < len; i++) {
    const idx = crypto.randomInt(PIN_CHARS.length);
    res += PIN_CHARS[idx];
  }
  return res;
}

export function cleanExpiredSessions(): void {
  const now = Date.now();
  for (const [code, session] of sessions.entries()) {
    // 60-second grace window after consumption for network retries
    if (session.status === "consumed" && session.consumedAt && now - session.consumedAt > 60000) {
      sessions.delete(code);
    } else if (now - session.createdAt > SESSION_TTL_MS) {
      sessions.delete(code);
    }
  }
}

export async function createSession(): Promise<SpotifySession> {
  cleanExpiredSessions();

  let code = generatePin(6);
  let attempts = 0;
  while (sessions.has(code) && attempts < 10) {
    code = generatePin(6);
    attempts++;
  }

  const session: SpotifySession = {
    code,
    status: "pending",
    createdAt: Date.now(),
  };

  sessions.set(code, session);
  return session;
}

export async function getSession(code: string): Promise<SpotifySession | null> {
  cleanExpiredSessions();
  const normalized = normalizePin(code);
  const s = sessions.get(normalized);
  if (!s) return null;
  if (Date.now() - s.createdAt > SESSION_TTL_MS) {
    sessions.delete(normalized);
    return null;
  }
  return s;
}

export async function setAuthorized(
  code: string,
  tokens: { accessToken: string; refreshToken: string; clientId?: string }
): Promise<boolean> {
  cleanExpiredSessions();
  const normalized = normalizePin(code);
  const s = sessions.get(normalized);
  if (!s) return false;

  s.status = "authorized";
  s.accessToken = tokens.accessToken;
  s.refreshToken = tokens.refreshToken;
  s.clientId = tokens.clientId;
  return true;
}

export async function consumeSession(code: string): Promise<SpotifySession | null> {
  cleanExpiredSessions();
  const normalized = normalizePin(code);
  const s = sessions.get(normalized);
  if (!s) return null;
  // Mark as consumed with a 60-second grace period for retries
  if (s.status === "authorized") {
    s.status = "consumed";
    s.consumedAt = Date.now();
  }
  return s;
}
