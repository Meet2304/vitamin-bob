import type { MetadataRoute } from "next";

// Static export: written once to manifest.webmanifest at build time.
export const dynamic = "force-static";

// public/ files are served under the base path (/website in Bob's copy), so prefix them here.
const base = process.env.SITE_BASE_PATH ?? "";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Vitamin Bob",
    short_name: "Vitamin Bob",
    description: "Care that starts with a missed call. Any phone, no internet, free for the patient.",
    start_url: `${base}/`,
    display: "standalone",
    background_color: "#c9e6c1",
    theme_color: "#c9e6c1",
    icons: [
      { src: `${base}/android-chrome-192x192.png`, sizes: "192x192", type: "image/png" },
      { src: `${base}/android-chrome-512x512.png`, sizes: "512x512", type: "image/png" },
    ],
  };
}
