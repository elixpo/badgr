import { NextResponse } from "next/server";
import { createSession } from "@/lib/spotifySessionStore";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const session = await createSession();
    const origin =
      process.env.NEXT_PUBLIC_SITE_URL ||
      request.headers.get("origin") ||
      new URL(request.url).origin ||
      "https://oreo.elixpo.com";

    const url = `${origin}/spotify?code=${session.code}`;

    return NextResponse.json(
      {
        status: "ok",
        code: session.code,
        url,
        expires_in: 600,
      },
      {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, OPTIONS",
          "Cache-Control": "no-store, no-cache, must-revalidate",
        },
      }
    );
  } catch (error) {
    return NextResponse.json(
      { status: "error", message: (error as Error).message },
      { status: 500 }
    );
  }
}

export async function OPTIONS() {
  return new NextResponse(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  });
}
