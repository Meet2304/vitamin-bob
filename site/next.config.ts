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
  // Plain <img> paths into public/ are not prefixed by Next, so components read the base path from here.
  env: { NEXT_PUBLIC_BASE_PATH: basePath },
};

export default nextConfig;
