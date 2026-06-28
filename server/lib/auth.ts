// Bearer-token gate for the MCP endpoint.
//
// This is a private tool. If MCP_BEARER_TOKEN is set in the environment, every
// request must send `Authorization: Bearer <token>`; anything else gets 401. If
// the variable is NOT set, the endpoint is open - convenient for local dev, and
// a deliberate choice so a fresh deploy works before you wire the secret. Set
// the token in Vercel before sharing the URL.

export function checkBearer(req: Request): Response | null {
  const required = process.env.MCP_BEARER_TOKEN;
  if (!required) return null; // no token configured -> open (dev / pre-secret)

  const header = req.headers.get("authorization") ?? "";
  const token = header.replace(/^Bearer\s+/i, "").trim();
  if (token && token === required) return null;

  return new Response(JSON.stringify({ error: "unauthorized" }), {
    status: 401,
    headers: { "content-type": "application/json", "www-authenticate": "Bearer" },
  });
}
