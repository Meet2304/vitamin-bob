/**
 * The people behind Bob, in speed-dial order. Photos live in public/images/team/:
 *   <slug>.webp      colour portrait, 640×800
 *   <slug>-lcd.png   the same crop dithered into seven LCD greens, 200×250 (drawn with pixelated scaling)
 * Social logos are from svglogos.dev, in public/images/logos/ (globe.svg, for personal sites, is drawn here).
 */
export type Member = {
  slug: string;
  name: string;
  /** Full name and role as on the summit deck's team slide. */
  fullName: string;
  role: string;
  email: string;
  linkedin: string;
  x: string;
  /** A personal site, shown as its own row on the contact card when there is one. */
  website?: string;
  /** That site's own logo, in public/images/logos/; the row falls back to a globe without one. */
  websiteLogo?: string;
};

export const MEMBERS: Member[] = [
  {
    slug: "meet",
    name: "Meet",
    fullName: "Meet Bhatt",
    role: "AI & Backend",
    email: "mbbhatt@andrew.cmu.edu",
    linkedin: "https://www.linkedin.com/in/meet-bhatt2304/",
    x: "https://x.com/Meet2304",
    website: "https://meetbhatt.com",
    websiteLogo: "/images/logos/meetbhatt.png", // meetbhatt.com's own app icon
  },
  {
    slug: "egshiglen",
    name: "Egshiglen",
    fullName: "Egshiglen Batjargal",
    role: "Policy & Data",
    email: "ebatjarg@andrew.cmu.edu",
    linkedin: "https://www.linkedin.com/in/egshiglen/",
    x: "https://x.com/egshigleennnn",
  },
  {
    slug: "yusril",
    name: "Yusril",
    fullName: "Yusril Hana",
    role: "Strategy & Impact",
    email: "mhana@andrew.cmu.edu",
    linkedin: "https://www.linkedin.com/in/yusrilhana/",
    x: "https://x.com/YusrilHana9",
  },
  {
    slug: "rizaldy",
    name: "Rizaldy",
    fullName: "Rizaldy Utomo",
    role: "Analytics & Research",
    email: "rutomo@andrew.cmu.edu",
    linkedin: "https://www.linkedin.com/in/rizaldykautsar/",
    x: "https://x.com/rzrizaldy",
  },
];

/** "https://www.linkedin.com/in/egshiglen/" → "in/egshiglen"; "https://x.com/rzrizaldy" → "@rzrizaldy" */
export const linkedinHandle = (url: string) =>
  url.replace(/^https?:\/\/(www\.)?linkedin\.com\//, "").replace(/\/$/, "");
/** "https://meetbhatt.com" → "meetbhatt.com" */
export const siteHandle = (url: string) => url.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "");
export const xHandle = (url: string) => `@${url.replace(/^https?:\/\/(www\.)?x\.com\//, "").replace(/\/$/, "")}`;
