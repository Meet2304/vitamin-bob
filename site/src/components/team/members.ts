/**
 * The people behind Bob, in speed-dial order. Photos live in public/images/team/:
 *   <slug>.webp      colour portrait, 640×800
 *   <slug>-lcd.png   the same crop dithered into seven LCD greens, 200×250 (drawn with pixelated scaling)
 * Social logos are from svglogos.dev, in public/images/logos/.
 */
export type Member = {
  slug: string;
  name: string;
  email: string;
  linkedin: string;
  x: string;
};

export const MEMBERS: Member[] = [
  {
    slug: "meet",
    name: "Meet",
    email: "mbbhatt@andrew.cmu.edu",
    linkedin: "https://www.linkedin.com/in/meet-bhatt2304/",
    x: "https://x.com/Meet2304",
  },
  {
    slug: "egshiglen",
    name: "Egshiglen",
    email: "ebatjarg@andrew.cmu.edu",
    linkedin: "https://www.linkedin.com/in/egshiglen/",
    x: "https://x.com/egshigleennnn",
  },
  {
    slug: "yusril",
    name: "Yusril",
    email: "mhana@andrew.cmu.edu",
    linkedin: "https://www.linkedin.com/in/yusrilhana/",
    x: "https://x.com/YusrilHana9",
  },
  {
    slug: "rizaldy",
    name: "Rizaldy",
    email: "rutomo@andrew.cmu.edu",
    linkedin: "https://www.linkedin.com/in/rizaldykautsar/",
    x: "https://x.com/rzrizaldy",
  },
];

/** "https://www.linkedin.com/in/egshiglen/" → "in/egshiglen"; "https://x.com/rzrizaldy" → "@rzrizaldy" */
export const linkedinHandle = (url: string) =>
  url.replace(/^https?:\/\/(www\.)?linkedin\.com\//, "").replace(/\/$/, "");
export const xHandle = (url: string) => `@${url.replace(/^https?:\/\/(www\.)?x\.com\//, "").replace(/\/$/, "")}`;
