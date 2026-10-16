import Link from "next/link";
import type { ReactNode } from "react";
import { MEMBERS } from "../team/members";
import { FooterBob } from "./FooterBob";
import { LogoChip } from "./Links";
import { SUMMIT, WINS } from "./Wins";

/**
 * The footer, on both pages: the brand and what it does, two short columns of links, and a bottom line with the
 * fine print a health tool must carry. It is the last stop when scrolling and snaps to the bottom of the screen.
 * Bob peeks over the divider and talks about whatever link you point at: each link's `say` is his line.
 */
const COLUMNS: {
  head: string;
  links: { label: string; short?: string; href: string; say: string; out?: boolean; logo?: string }[];
}[] = [
  {
    head: "Explore",
    links: [
      { label: "Why it matters", href: "/#problem", say: "4.6 billion reasons." },
      { label: "How it works", href: "/#fix", say: "Ring once. I call back." },
      { label: "Recognition", href: "/#recognition", say: "Next stop: Seoul!" },
      { label: "The team", href: "/team", say: "Meet my four humans." },
    ],
  },
  {
    head: "Connect",
    links: [
      {
        label: "GitHub",
        short: "GitHub",
        href: "https://github.com/Meet2304/vitamin-bob",
        say: "Every line of me is open.",
        out: true,
        logo: "/images/logos/github-icon.svg",
      },
      {
        label: "World Bank Group post",
        short: "LinkedIn",
        href: WINS[0].href,
        say: "Our big weekend!",
        out: true,
        logo: "/images/logos/linkedin-icon.svg",
      },
      {
        label: "Email the team",
        short: "Email",
        href: `mailto:${MEMBERS.map((m) => m.email).join(",")}`,
        say: "They always write back.",
        logo: "/images/logos/google-gmail.svg",
      },
    ],
  },
];

function FootLink({
  href,
  say,
  out,
  logo,
  short,
  children,
}: {
  href: string;
  say: string;
  out?: boolean;
  logo?: string;
  short?: string;
  children: ReactNode;
}) {
  // phones show the short label under the logo (a row of tiles); wider screens, the full label beside it
  const label = (
    <>
      {logo && <LogoChip src={logo} alt="" />}
      {short ? (
        <>
          <span className="md:hidden">{short}</span>
          <span className="hidden md:inline">{children}</span>
        </>
      ) : (
        <span>{children}</span>
      )}
    </>
  );
  if (out)
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className="foot-link" data-say={say}>
        {label}
        <span aria-hidden className="hidden md:inline">
          ↗
        </span>
      </a>
    );
  if (href.startsWith("mailto:"))
    return (
      <a href={href} className="foot-link" data-say={say}>
        {label}
      </a>
    );
  return (
    <Link href={href} className="foot-link" data-say={say}>
      {label}
    </Link>
  );
}

export function Footer() {
  return (
    <footer className="site-footer bg-px text-lcd">
      <div className="mx-auto w-full max-w-[1280px] px-6 pt-6 pb-5 md:px-12 md:pt-16 md:pb-8">
        <div className="grid grid-cols-1 gap-y-5 md:grid-cols-[1.5fr_1fr_1fr_13rem] md:gap-x-12 md:gap-y-10">
          <div className="md:pb-12">
            <span className="text-[24px] font-bold tracking-tight">Vitamin Bob</span>
            <p className="mt-1 font-semibold text-accent-hi md:mt-3">Listen. Guide. Connect.</p>
            <p className="mt-2 hidden max-w-[380px] text-[15px] leading-relaxed opacity-85 md:block">
              A free phone call, in your own language, that gets patients and their story to the right care.
            </p>
            <p className="mt-5 hidden border border-lcd/40 px-2.5 py-1 font-mono text-[11px] tracking-wide md:inline-block">
              Ignite talk · {SUMMIT.event}
            </p>
          </div>

          {COLUMNS.map((c) => (
            <nav key={c.head} aria-label={c.head} className="md:pb-12">
              <h2 className="font-mono text-[12px] font-medium tracking-wider text-accent-hi uppercase">{c.head}</h2>
              <ul
                className={`mt-3 flex flex-col gap-2.5 text-[15px] md:mt-4 ${c.head === "Explore" ? "foot-pills" : "foot-tiles"}`}
              >
                {c.links.map((l) => (
                  <li key={l.label}>
                    <FootLink href={l.href} say={l.say} out={l.out} logo={l.logo} short={l.short}>
                      {l.label}
                    </FootLink>
                  </li>
                ))}
              </ul>
            </nav>
          ))}

          <div className="mt-1 min-w-0 self-end md:mt-0">
            <FooterBob />
          </div>
        </div>

        <div className="flex flex-col gap-2 border-t-4 border-lcd pt-5 font-mono text-[11px] leading-relaxed md:flex-row md:items-center md:justify-between md:gap-10 md:text-[12px]">
          <p className="max-w-[720px] opacity-70">
            Not a diagnostic tool. The triage protocol is drafted from WHO IMCI and has not yet been reviewed by a
            clinician.
          </p>
          <p className="shrink-0 opacity-70">
            © 2026 The Vitamin Bob team<span className="hidden md:inline"> · </span>
            <span className="block text-accent-hi md:inline">Made by Humans, on Earth</span>
          </p>
        </div>
      </div>
    </footer>
  );
}
