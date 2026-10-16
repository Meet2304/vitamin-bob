import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Space_Grotesk } from "next/font/google";
import Script from "next/script";
import "./globals.css";

// Readable type on a pixel screen: the LCD look comes from the glass, the dithering and the sprites.
const display = Space_Grotesk({ variable: "--font-space-grotesk", subsets: ["latin"] });
const mono = IBM_Plex_Mono({ variable: "--font-plex-mono", subsets: ["latin"], weight: ["400", "500", "600"] });

const title = "Vitamin Bob · Access to care begins before the clinic";
const description =
  "Listen. Guide. Connect. A free call in your own language, on any phone: no app, no internet. A small AI listens, gives a clear next step, and sends your story to the clinic before you arrive. Clinicians make the care decision.";

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
    // `js` is added before first paint so screens can hide their pieces until they move in (globals.css, `.rise`);
    // without scripts nothing is hidden. React would flag the extra class, hence suppressHydrationWarning.
    <html lang="en" className={`${display.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: "document.documentElement.classList.add('js')" }} />
      </head>
      <body className="min-h-screen">
        {children}
        <Script src="https://www.googletagmanager.com/gtag/js?id=G-E8QCZDYMWC" strategy="afterInteractive" />
        <Script id="google-analytics" strategy="afterInteractive">
          {`
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'G-E8QCZDYMWC');
          `}
        </Script>
      </body>
    </html>
  );
}
