import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  return proxyRequest(request);
}

export async function POST(request: NextRequest) {
  return proxyRequest(request);
}

export async function PUT(request: NextRequest) {
  return proxyRequest(request);
}

export async function DELETE(request: NextRequest) {
  return proxyRequest(request);
}

export async function PATCH(request: NextRequest) {
  return proxyRequest(request);
}

async function proxyRequest(request: NextRequest) {
  const backendUrl = process.env.BACKEND_URL;

  if (!backendUrl) {
    return NextResponse.json(
      { error: "BACKEND_URL not configured" },
      { status: 502 }
    );
  }

  // Extract the API path from the URL (e.g., /api/auth/login)
  const url = new URL(request.url);
  const apiPath = url.pathname + url.search;
  const targetUrl = `${backendUrl}${apiPath}`;

  // Forward request to backend
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("content-length");

  const body = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : await request.arrayBuffer();

  const res = await fetch(targetUrl, {
    method: request.method,
    headers,
    body,
  });

  // Build response, forwarding all headers including Set-Cookie correctly
  // Headers.forEach may not handle multiple Set-Cookie headers properly,
  // so we use getSetCookie() for cookies and forEach for the rest.
  const responseHeaders = new Headers();
  const setCookies = res.headers.getSetCookie?.() ?? [];
  for (const cookie of setCookies) {
    responseHeaders.append("set-cookie", cookie);
  }
  res.headers.forEach((value, key) => {
    if (key.toLowerCase() !== "set-cookie") {
      responseHeaders.set(key, value);
    }
  });

  return new NextResponse(res.body, {
    status: res.status,
    headers: responseHeaders,
  });
}
