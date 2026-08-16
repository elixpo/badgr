import { NextResponse } from "next/server";
import { setAuthorized } from "@/lib/spotifySessionStore";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const origin =
    process.env.NEXT_PUBLIC_SITE_URL ||
    request.headers.get("origin") ||
    new URL(request.url).origin ||
    "https://oreo.elixpo.com";

  try {
    const { searchParams } = new URL(request.url);
    const code = searchParams.get("code");
    const state = searchParams.get("state") || "";
    const error = searchParams.get("error");

    if (error) {
      return NextResponse.redirect(`${origin}/spotify?error=${encodeURIComponent(error)}`);
    }

    if (!code) {
      return NextResponse.redirect(`${origin}/spotify?error=Missing+authorization+code`);
    }

    const clientId = process.env.SPOTIFY_CLIENT_ID;
    const clientSecret = process.env.SPOTIFY_CLIENT_SECRET;

    if (!clientId || !clientSecret) {
      return NextResponse.redirect(
        `${origin}/spotify?error=Server+misconfigured+(missing+credentials)`
      );
    }

    const redirectUri = `${origin}/api/spotify/callback`;
    const basicAuth = Buffer.from(`${clientId}:${clientSecret}`).toString("base64");

    const tokenRes = await fetch("https://accounts.spotify.com/api/token", {
      method: "POST",
      headers: {
        "Authorization": `Basic ${basicAuth}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({
        grant_type: "authorization_code",
        code,
        redirect_uri: redirectUri,
      }),
      cache: "no-store",
    });

    const tokenData = await tokenRes.json();

    if (!tokenRes.ok || !tokenData.access_token) {
      const msg = tokenData.error_description || tokenData.error || "Token exchange failed";
      return NextResponse.redirect(`${origin}/spotify?error=${encodeURIComponent(msg)}`);
    }

    // Save tokens in session for the badge to pick up
    if (state) {
      const ok = await setAuthorized(state, {
        accessToken: tokenData.access_token,
        refreshToken: tokenData.refresh_token || "",
        clientId,
      });
      if (!ok) {
        return NextResponse.redirect(`${origin}/spotify?error=Session+expired+or+invalid`);
      }
    }

    return NextResponse.redirect(`${origin}/spotify/success?code=${encodeURIComponent(state)}`);
  } catch (err) {
    const msg = (err as Error).message || "Internal error";
    return NextResponse.redirect(`${origin}/spotify?error=${encodeURIComponent(msg)}`);
  }
}
