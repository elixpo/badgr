/* Single source of truth for the app catalogue surfaced on the site.
 * Mirrors the manifest.json files shipped on the badge.
 *
 *   slug      — the on-disk app directory ("Oreo Pet", "snake", …)
 *   urlSlug   — URL-safe variant used by /apps/[urlSlug]/ routes
 *   pngIcon   — path under /public/icons (real asset; pixel-art LCD icon)
 *   icon      — Lucide string fallback when the PNG fails to load
 *   version   — last published manifest version
 *   author    — manifest.author; defaults to @Circuit-Overtime
 *   details   — long-form pitch used on the detail page; falls back to
 *               `blurb` if absent. Markdown is NOT parsed here — plain
 *               paragraphs separated by \n\n.
 */

export type AppIconId =
  | "Contact" | "Bird"     | "Image"      | "Worm"      | "Compass"
  | "BookOpen"| "Car"      | "Cloud"      | "GitCommit" | "User"
  | "Gamepad2"| "HardDrive"| "Palette"    | "PawPrint"  | "Cpu"
  | "Wifi"    | "Bluetooth"| "RefreshCw"  | "Settings"  | "Music"
  | "Flame";

export type AppEntry = {
  slug:      string;
  urlSlug:   string;
  name:      string;
  blurb:     string;
  details?:  string;
  category:  "core" | "game" | "tool" | "store";
  tint:      "primary" | "teal" | "gold" | "lilac";
  icon:      AppIconId;
  pngIcon?:  string;
  version?:  string;
  author?:   string;
};

const DEFAULT_AUTHOR  = "@Circuit-Overtime";
const DEFAULT_VERSION = "0.1";

/* Convert a badge dir slug into a URL-safe identifier — lowercase,
 * spaces → hyphens, strip everything else. Used at both data-entry
 * time below and at lookup time on the detail route. */
export function toUrlSlug(slug: string): string {
  return slug.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");
}

import manifestsData from "./manifests.json";

type ManifestData = { name?: string; description?: string; icon?: string; version?: string; author?: string; };
const manifests: Record<string, ManifestData> = manifestsData;

function app(
  slug: string,
  rest: Omit<AppEntry, "slug" | "urlSlug" | "name" | "blurb" | "author" | "version" | "pngIcon"> &
        Partial<Pick<AppEntry, "name" | "blurb" | "author" | "version" | "pngIcon">>,
): AppEntry {
  const m = manifests[slug] || {};
  return {
    slug,
    urlSlug: toUrlSlug(slug),
    name: m.name ?? rest.name ?? slug,
    blurb: m.description ?? rest.blurb ?? "",
    pngIcon: m.icon ? `/icons/${m.icon}` : rest.pngIcon,
    author:  m.author ?? rest.author ?? DEFAULT_AUTHOR,
    version: m.version ?? rest.version ?? DEFAULT_VERSION,
    ...rest,
  };
}

export const PRELOADED: AppEntry[] = [
  app("badge",   { category: "core", tint: "primary", icon: "Contact",
    details: "Your digital identity card. Live GitHub stats pulled from your handle " +
             "(set in secrets.py), QR code for your contact card, and a configurable " +
             "tagline. Designed to be held up at conferences and read across a table." }),
  app("flappy",  { category: "game", tint: "lilac",   icon: "Bird",
    details: "A two-button Flappy clone with the Oreo mascot as the protagonist. " +
             "Procedurally-generated pipe pairs, parallax scrolling background, " +
             "and a hi-score stored on flash so it survives reboot." }),
  app("gallery", { category: "core", tint: "gold",    icon: "Image",
    details: "Renders RGB565 .py modules baked from your raw PNGs by " +
             "`tools/optimize_assets.py`, OR `.r565` binaries dropped in via the " +
             "WiFi file-transfer flow. Auto-hides the UI after 2 s so it doubles " +
             "as a slideshow when you're not touching anything." }),
  app("snake",   { category: "game", tint: "teal",    icon: "Worm",
    details: "Classic grid-based Snake. Speeds up the longer you survive. Pixel " +
             "rendering uses framebuf rect fills directly — runs at a solid 30 fps " +
             "even with a 200-segment tail." }),
  app("quest",   { category: "game", tint: "primary", icon: "Compass",
    details: "Walk around the conference floor with your badge held up. Each IR " +
             "beacon you find awards a token. Visit a friend's badge in scanner " +
             "mode and trade tokens to complete the set." }),
  app("reader",  { category: "tool", tint: "lilac",   icon: "BookOpen",
    details: "Lightweight markdown renderer supporting headings, lists, code blocks, " +
             "and inline emphasis. Files arrive via the WiFi transfer flow and land " +
             "in `documents/`. Scrolling is UP/DOWN, page-skip is LEFT/RIGHT." }),
];

export const ALL_APPS: AppEntry[] = [
  ...PRELOADED,
  app("racer",    { category: "game", tint: "primary", icon: "Car",
    details: "Endless top-down racer with procedurally-generated track curvature. " +
             "Boost cooldown of 3 s, point multiplier scales with speed." }),
  app("weather",  { category: "tool", tint: "teal",    icon: "Cloud",
    details: "OpenWeatherMap-backed. Cached on disk with a TTL so the forecast " +
             "survives offline windows. Set OWM_API_KEY in your .env." }),
  app("commits",  { category: "tool", tint: "gold",    icon: "GitCommit",
    details: "Pulls the public events stream for a configurable list of repos. " +
             "Renders each commit as a card with author, message, and timestamp." }),

  app("gamepad",  { category: "tool", tint: "primary", icon: "Gamepad2",
    details: "HID Gamepad over BLE — your laptop sees the badge as a generic " +
             "gamepad. Maps the badge buttons to standard XInput buttons." }),
  app("storage",  { category: "tool", tint: "lilac",   icon: "HardDrive",
    details: "System Monitor app with a 2-tab interface. Tab 0 provides a visual breakdown of flash usage across apps and assets. Tab 1 monitors live MicroPython heap usage and supports one-tap Garbage Collection." }),
  app("wifi",     { category: "core", tint: "teal",    icon: "Wifi",
    details: "Manage saved networks with per-entry priority and metered flags. " +
             "Run ping + speed test from the same screen. Send-files row exposes " +
             "the on-device upload URL." }),
  app("bt",       { category: "core", tint: "lilac",   icon: "Bluetooth",
    details: "Coming soon. The underlying BLE stack ships paired-device storage " +
             "and an SMP handshake — we're holding the UI back until peer-presence " +
             "features land in a real user flow." }),
  app("updates",  { category: "core", tint: "gold",    icon: "RefreshCw",
    details: "Pulls release manifests from the project repo on a 6-hour cadence. " +
             "Three-state model — LTS (current), BETA (newer pre-release), OUTDATED " +
             "(older than current). Manual check is always available." }),
  app("settings", { category: "core", tint: "primary", icon: "Settings",
    details: "Top-level settings hub. Drills into WiFi / Bluetooth / Gestures / " +
             "Updates as needed; persists every preference to flash." }),
  app("Colors",   { category: "tool", tint: "lilac",   icon: "Palette",
    details: "Multi-slot real-time palette designer. Customize Primary, Background, Card, " +
             "Secondary, and Accent colors with automatic contrast inversion and live OS preview." }),
];

export const STORE: AppEntry[] = [
  app("spotify",  { category: "store", tint: "teal",    icon: "Music",
    details: "Production Spotify Web API controller with live album cover photo rendering, " +
             "debounced volume slider, library drawer navigation, and zero-friction 6-digit cloud PIN pairing." }),
  app("doom",     { category: "store", tint: "primary", icon: "Flame",
    details: "Authentic id Software DOOM engine port (E1M1 Hangar) featuring 1:1 pixel rendering, " +
             "multi-tick button event queues, full weapon cycling, and fullscreen gaming." }),
  app("Oreo Pet", { category: "store", tint: "primary", icon: "PawPrint",
    blurb:   "Tamagotchi panda. Feed, play, sleep, repeat.",
    details: "A virtual panda you have to care for. Three stats: happiness, hunger, " +
             "cleanliness — all degrade over real wallclock time, so neglecting the " +
             "badge for a week genuinely matters. Autonomous mood-driven idle animations." }),
];

/* Flat list used by the [slug] route's generateStaticParams and the
 * detail-page lookup. */
export const ALL_CATALOG: AppEntry[] = [...ALL_APPS, ...STORE];

export function findApp(urlSlug: string): AppEntry | undefined {
  return ALL_CATALOG.find(a => a.urlSlug === urlSlug);
}
