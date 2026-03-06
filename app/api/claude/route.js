// Rate limiting: simple in-memory store (resets on deploy)
const rateLimitMap = new Map();
const RATE_LIMIT_WINDOW = 60 * 1000; // 1 minute
const RATE_LIMIT_MAX = 20; // max requests per window

function checkRateLimit(ip) {
  const now = Date.now();
  const entry = rateLimitMap.get(ip);

  if (!entry || now - entry.start > RATE_LIMIT_WINDOW) {
    rateLimitMap.set(ip, { start: now, count: 1 });
    return true;
  }

  if (entry.count >= RATE_LIMIT_MAX) {
    return false;
  }

  entry.count++;
  return true;
}

// Allowed Claude models
const ALLOWED_MODELS = [
  "claude-sonnet-4-20250514",
  "claude-haiku-4-5-20251001",
  "claude-opus-4-6",
];

// Max tokens cap
const MAX_TOKENS_CAP = 16000;

export async function POST(request) {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return Response.json(
      { error: "ANTHROPIC_API_KEY is not configured" },
      { status: 500 }
    );
  }

  // Origin check: only allow same-origin or Vercel preview URLs
  const origin = request.headers.get("origin") || "";
  const host = request.headers.get("host") || "";
  if (origin && !origin.includes(host) && !origin.includes("vercel.app")) {
    return Response.json({ error: "Forbidden" }, { status: 403 });
  }

  // Rate limiting
  const ip =
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    request.headers.get("x-real-ip") ||
    "unknown";
  if (!checkRateLimit(ip)) {
    return Response.json(
      { error: "Rate limit exceeded. Try again later." },
      { status: 429 }
    );
  }

  try {
    const body = await request.json();

    // Validate model
    if (body.model && !ALLOWED_MODELS.includes(body.model)) {
      return Response.json(
        { error: `Model not allowed: ${body.model}` },
        { status: 400 }
      );
    }

    // Cap max_tokens
    if (body.max_tokens && body.max_tokens > MAX_TOKENS_CAP) {
      body.max_tokens = MAX_TOKENS_CAP;
    }

    const resp = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2025-04-15",
      },
      body: JSON.stringify(body),
    });

    const data = await resp.json();

    if (!resp.ok) {
      return Response.json(data, { status: resp.status });
    }

    return Response.json(data);
  } catch (e) {
    return Response.json({ error: e.message }, { status: 500 });
  }
}
