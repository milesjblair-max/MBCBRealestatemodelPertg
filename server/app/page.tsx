// A small landing page so the deploy URL is self-explanatory: what this is, the
// MCP endpoint, the tools, and how to connect a client. Pure server component.

const TOOLS: { name: string; what: string }[] = [
  { name: "estimate_price", what: "Likely price + range for a WA house (suburb, land, beds, baths, condition)." },
  { name: "assess_property", what: "Estimate plus a buyer-fit read with pros and cons." },
  { name: "forecast", what: "Bear/base/bull scenario fan to Mid-29 + headline metrics." },
  { name: "list_suburbs", what: "The suburbs the engine knows, with medians and in-band flag." },
  { name: "onboarding_questions", what: "The questions to ask a new buyer before resolving a profile." },
  { name: "resolve_profile", what: "Profile -> budget band, buy-timing posture, normalised weights." },
  { name: "rank_suburbs_for_profile", what: "Rank suburbs for a specific buyer (their anchor, criteria, budget)." },
  { name: "match_listings", what: "Match listings to a buyer's filters, ranked by fit." },
  { name: "search_listings", what: "Live for-sale houses with photos (RapidAPI; sample fallback)." },
];

const card: React.CSSProperties = {
  border: "1px solid #25302e",
  borderRadius: 10,
  padding: "14px 16px",
  background: "#141a19",
};

export default function Home() {
  return (
    <main style={{ maxWidth: 820, margin: "0 auto", padding: "48px 22px 80px" }}>
      <p style={{ color: "#3aa6a0", fontWeight: 600, letterSpacing: ".04em", margin: 0 }}>MODEL CONTEXT PROTOCOL SERVER</p>
      <h1 style={{ fontSize: 30, margin: "8px 0 6px" }}>Como home model - Phase 2</h1>
      <p style={{ color: "#9fb0ad", marginTop: 0 }}>
        The WA (Perth) house-price and suburb-fit engine from Phase 1, exposed as MCP tools over Streamable HTTP. The
        engine is parity-tested to the dollar against the Python reference; this server is the typed contract around it.
      </p>

      <div style={{ ...card, marginTop: 22 }}>
        <div style={{ color: "#9fb0ad", fontSize: 13 }}>MCP endpoint</div>
        <code style={{ fontSize: 16, color: "#7fd9d2" }}>POST /api/mcp</code>
        <div style={{ color: "#7f908d", fontSize: 12.5, marginTop: 8 }}>
          Streamable HTTP, stateless. Send <code>Authorization: Bearer &lt;token&gt;</code> when{" "}
          <code>MCP_BEARER_TOKEN</code> is set. Live listings need <code>RAPIDAPI_KEY</code>.
        </div>
      </div>

      <h2 style={{ fontSize: 19, marginTop: 30 }}>Tools</h2>
      <div style={{ display: "grid", gap: 8 }}>
        {TOOLS.map((t) => (
          <div key={t.name} style={card}>
            <code style={{ color: "#7fd9d2" }}>{t.name}</code>
            <div style={{ color: "#9fb0ad", fontSize: 13.5, marginTop: 3 }}>{t.what}</div>
          </div>
        ))}
      </div>

      <h2 style={{ fontSize: 19, marginTop: 30 }}>Connect a client</h2>
      <pre style={{ ...card, overflowX: "auto", fontSize: 13 }}>
        {`{
  "mcpServers": {
    "como-home-model": {
      "url": "https://<this-deployment>/api/mcp",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}`}
      </pre>

      <p style={{ color: "#7f908d", fontSize: 12, marginTop: 28 }}>
        General information only, not financial, legal or tax advice. Figures are mid-2026 approximations; forecasts are
        scenario estimates, not predictions.
      </p>
    </main>
  );
}
