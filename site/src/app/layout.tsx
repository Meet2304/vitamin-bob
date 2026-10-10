import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Space_Grotesk } from "next/font/google";
import "./globals.css";

// Readable type on a pixel screen: the LCD look comes from the glass, the dithering and the sprites.
const display = Space_Grotesk({ variable: "--font-space-grotesk", subsets: ["latin"] });
const mono = IBM_Plex_Mono({ variable: "--font-plex-mono", subsets: ["latin"], weight: ["400", "500", "600"] });

const title = "Vitamin Bob · Press 1 for care";
const description =
  "A free phone line to the right clinic. Any phone, no internet, Hindi and Gujarati. On-device Gemma 4 listens, transparent rules decide, and a person makes the call on anything unsure.";

// Icons and the share image come from the file conventions in this folder (favicon.ico, icon1/2.png,
// apple-icon.png, opengraph-image.jpg, twitter-image.jpg, manifest.ts). Share images need absolute URLs.
export const metadata: Metadata = {
  metadataBase: new URL(process.env.SITE_URL ?? "https://vitamin-bob.vercel.app"),
  title,
  description,
  openGraph: { type: "website", siteName: "Vitamin Bob", title, description, url: "/" },
  twitter: { card: "summary_large_image", title, description },
};

export const viewport: Viewport = {
  themeColor: "#c9e6c1",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${display.variable} ${mono.variable}`}>
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
