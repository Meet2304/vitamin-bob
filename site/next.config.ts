import type { NextConfig } from "next";

// One source, two homes:
//   Vercel / any static host: served at the domain root (no base path).
//   Bob's local server:       served at /website, next to /dashboard/live (npm run build:bob).
const basePath = process.env.SITE_BASE_PATH ?? "";

const nextConfig: NextConfig = {
  // A fully static site: `npm run build` writes ./out, which any static host can serve.
  output: "export",
  basePath,
  trailingSlash: true,
};

export default nextConfig;
