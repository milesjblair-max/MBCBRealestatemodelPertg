import type { ReactNode } from "react";

export const metadata = {
  title: "Como home model - MCP server",
  description: "The Como WA house-price and suburb-fit engine, exposed as a Model Context Protocol server.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          background: "#0f1413",
          color: "#e7efee",
          fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial",
          lineHeight: 1.55,
        }}
      >
        {children}
      </body>
    </html>
  );
}
