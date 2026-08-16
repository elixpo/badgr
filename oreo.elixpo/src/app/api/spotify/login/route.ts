import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const SCOPES = "user-read-playback-state user-modify-playback-state user-read-currently-playing user-library-read user-read-recently-played user-top-read playlist-read-private playlist-read-collaborative";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const code = searchParams.get("code") || "";

    const clientId = process.env.SPOTIFY_CLIENT_ID;
    if (!clientId) {
      return new NextResponse(
        "Server configuration error: SPOTIFY_CLIENT_ID is not set in environment variables.",
        { status: 500 }
      );
    }

    const origin =
      process.env.NEXT_PUBLIC_SITE_URL ||
      request.headers.get("origin") ||
      new URL(request.url).origin ||
      "https://oreo.elixpo.com";

    const redirectUri = `${origin}/api/spotify/callback`;

    const params = new URLSearchParams({
      response_type: "code",
      client_id: clientId,
      scope: SCOPES,
      redirect_uri: redirectUri,
      state: code,
    });

    return NextResponse.redirect(`https://accounts.spotify.com/authorize?${params.toString()}`);
  } catch (error) {
    return new NextResponse((error as Error).message, { status: 500 });
  }
}
