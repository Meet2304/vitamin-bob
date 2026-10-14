import type { Metadata } from "next";
import { SoftKeys, StatusBar } from "@/components/lcd/Phone";
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
      <StatusBar />
      <main>
        <TeamHero />
        <Contacts />
      </main>
      <SoftKeys
        left={{ href: "/", label: "◀ BACK" }}
        hint="press 1–4 to speed dial, 0 to go back"
        right={{ href: "#contacts", label: "CONTACTS" }}
      />
    </>
  );
}
