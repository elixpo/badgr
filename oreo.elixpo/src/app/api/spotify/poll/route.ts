import { NextResponse } from "next/server";
import { getSession, consumeSession } from "@/lib/spotifySessionStore";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const code = searchParams.get("code");

    if (!code) {
      return NextResponse.json(
        { status: "error", message: "Missing code parameter" },
        { status: 400 }
      );
    }

    const session = await getSession(code);
    if (!session) {
      return NextResponse.json(
        { status: "expired", message: "Session expired or invalid" },
        {
          headers: {
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-store, no-cache, must-revalidate",
          },
        }
      );
    }

    if (session.status === "authorized") {
      // Consume and return tokens
      await consumeSession(code);
      return NextResponse.json(
        {
          status: "authorized",
          access_token: session.accessToken,
          refresh_token: session.refreshToken,
          client_id: session.clientId,
        },
        {
          headers: {
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-store, no-cache, must-revalidate",
          },
        }
      );
    }

    // Still pending
    return NextResponse.json(
      { status: "pending" },
      {
        headers: {
          "Access-Control-Allow-Origin": "*",
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
