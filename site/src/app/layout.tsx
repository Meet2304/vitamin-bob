import type { Metadata } from "next";
import { IBM_Plex_Mono, Space_Grotesk } from "next/font/google";
import "./globals.css";

// Readable type on a pixel screen: the LCD look comes from the glass, the dithering and the sprites.
const display = Space_Grotesk({ variable: "--font-space-grotesk", subsets: ["latin"] });
const mono = IBM_Plex_Mono({ variable: "--font-plex-mono", subsets: ["latin"], weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  title: "Vitamin Bob · Press 1 for care",
  description:
    "A free phone line to the right clinic. Any phone, no internet, Hindi and Gujarati. On-device Gemma 4 listens, transparent rules decide, and a person makes the call on anything unsure.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${display.variable} ${mono.variable}`}>
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
