/** @type {import('next').NextConfig} */
const nextConfig = {
  // The vendored engine (server/lib/engine) uses NodeNext-style ESM import
  // specifiers - it imports "./util.js" to mean util.ts. Teach webpack to
  // resolve a ".js" specifier to the ".ts" source so the engine compiles
  // unchanged. (tsx already does this for the parity tests.)
  webpack: (config) => {
    config.resolve.extensionAlias = {
      ".js": [".ts", ".tsx", ".js", ".jsx"],
      ".mjs": [".mts", ".mjs"],
      ...(config.resolve.extensionAlias ?? {}),
    };
    return config;
  },
};

export default nextConfig;
