import type { Metadata } from "next";
import { BoothDemo } from "@/components/demo/BoothDemo";
import { Footer } from "@/components/lcd/Footer";
import { StatusBar } from "@/components/lcd/Phone";

const title = "Try the demo · Vitamin Bob";
const description =
  "Be Kevin for one minute: ring once from a basic phone, answer Vitamin Bob's call in one of six languages, and see the next step. Runs in your browser, no internet needed.";

export const metadata: Metadata = {
  title,
  description,
  openGraph: { type: "website", siteName: "Vitamin Bob", title, description, url: "/demo/" },
  twitter: { card: "summary_large_image", title, description },
};

export default function DemoPage() {
  return (
    <>
      <StatusBar page="demo" />
      <main>
        <BoothDemo />
      </main>
      <Footer />
    </>
  );
}
