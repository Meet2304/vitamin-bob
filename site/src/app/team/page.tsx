import type { Metadata } from "next";
import { Footer } from "@/components/lcd/Footer";
import { StatusBar } from "@/components/lcd/Phone";
import { Contacts, TeamHero } from "@/components/team/Team";

const title = "The team · Vitamin Bob";
const description =
  "Egshiglen, Meet, Rizaldy and Yusril built Vitamin Bob. Say hello: email, LinkedIn and X for each of us.";

// The share image is opengraph-image.jpg / twitter-image.jpg in this folder (file convention).
export const metadata: Metadata = {
  title,
  description,
  openGraph: { type: "website", siteName: "Vitamin Bob", title, description, url: "/team/" },
  twitter: { card: "summary_large_image", title, description },
};

export default function TeamPage() {
  return (
    <>
      <StatusBar page="team" />
      <main>
        <TeamHero />
        <Contacts />
      </main>
      <Footer />
    </>
  );
}
