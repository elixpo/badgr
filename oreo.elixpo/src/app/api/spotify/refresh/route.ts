import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    const refreshToken = body.refresh_token;

    if (!refreshToken) {
      return NextResponse.json(
        { status: "error", message: "Missing refresh_token in request body" },
        {
          status: 400,
          headers: {
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-store, no-cache, must-revalidate",
          },
        }
      );
    }

    return await handleRefresh(refreshToken);
  } catch (err) {
    return NextResponse.json(
      { status: "error", message: (err as Error).message || "Internal error" },
      {
        status: 500,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Cache-Control": "no-store, no-cache, must-revalidate",
        },
      }
    );
  }
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const refreshToken = searchParams.get("refresh_token");

    if (!refreshToken) {
      return NextResponse.json(
        { status: "error", message: "Missing refresh_token query parameter" },
        {
          status: 400,
          headers: {
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-store, no-cache, must-revalidate",
          },
        }
      );
    }

    return await handleRefresh(refreshToken);
  } catch (err) {
    return NextResponse.json(
      { status: "error", message: (err as Error).message || "Internal error" },
      {
        status: 500,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Cache-Control": "no-store, no-cache, must-revalidate",
        },
      }
    );
  }
}

async function handleRefresh(refreshToken: string) {
  const clientId = process.env.SPOTIFY_CLIENT_ID;
  const clientSecret = process.env.SPOTIFY_CLIENT_SECRET;

  if (!clientId || !clientSecret) {
    return NextResponse.json(
      { status: "error", message: "Server misconfigured: missing Spotify credentials" },
      {
        status: 500,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Cache-Control": "no-store, no-cache, must-revalidate",
        },
      }
    );
  }

  const basicAuth = Buffer.from(`${clientId}:${clientSecret}`).toString("base64");

  const tokenRes = await fetch("https://accounts.spotify.com/api/token", {
    method: "POST",
    headers: {
      "Authorization": `Basic ${basicAuth}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: refreshToken,
    }),
    cache: "no-store",
  });

  const tokenData = await tokenRes.json();

  if (!tokenRes.ok || !tokenData.access_token) {
    const errorMsg = tokenData.error_description || tokenData.error || "Failed to refresh token";
    return NextResponse.json(
      {
        status: "error",
        error: tokenData.error || "invalid_grant",
        message: errorMsg,
      },
      {
        status: tokenRes.status || 400,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Cache-Control": "no-store, no-cache, must-revalidate",
        },
      }
    );
  }

  return NextResponse.json(
    {
      status: "ok",
      access_token: tokenData.access_token,
      token: tokenData.access_token,
      refresh_token: tokenData.refresh_token || refreshToken,
      expires_in: tokenData.expires_in || 3600,
      token_type: tokenData.token_type || "Bearer",
      scope: tokenData.scope || "",
      client_id: clientId,
    },
    {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "no-store, no-cache, must-revalidate",
      },
    }
  );
}

export async function OPTIONS() {
  return new NextResponse(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  });
}
