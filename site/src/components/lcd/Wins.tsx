import { FlyArrow, LogoChip } from "./Links";
import { LinkedInEmbed } from "./LinkedInEmbed";
import { Screen } from "./Phone";

/**
 * The two wins: a badge in the hero, and a screen with the announcements. Only the World Bank post can be
 * embedded; Hack-Nation's is a link. Wording follows the two LinkedIn posts.
 */
const WINS = [
  {
    org: "HACK-NATION",
    title: "Grand winner",
    event: "7th Global AI Hackathon",
    detail: "24 hours, 3,000+ builders, one grand winner.",
    href: "https://www.linkedin.com/posts/hack-nation_hacknation-globalaihackathon-buildinpublic-activity-7515871527326699520-EMsF",
  },
  {
    org: "WORLD BANK GROUP",
    title: "Health Track winner",
    event: "Small AI for Development Hackathon Challenge",
    detail: "AI that lowers barriers to care by understanding patients in their own language.",
    href: "https://www.linkedin.com/feed/update/urn:li:ugcPost:7516077076857389056/",
  },
];
const WB_EMBED = "https://www.linkedin.com/embed/feed/update/urn:li:ugcPost:7516077076857389056?collapsed=1";

/** A pixel trophy on the same crisp grid as Bob, with three sparkles that light up in turn. */
export function Trophy({ px = 4, sparkle = true }: { px?: number; sparkle?: boolean }) {
  const cup: [number, number, number, number][] = [
    [3, 1, 8, 1], // rim
    [3, 2, 8, 4], // bowl
    [4, 6, 6, 1],
    [5, 7, 4, 1],
    [6, 8, 2, 2], // stem
    [4, 10, 6, 1], // base
    [3, 11, 8, 1],
    [1, 2, 2, 1], // handles
    [1, 3, 1, 2],
    [1, 5, 2, 1],
    [11, 2, 2, 1],
    [12, 3, 1, 2],
    [11, 5, 2, 1],
  ];
  const sparkles: [number, number][] = [
    [0, 0],
    [13, 0],
    [14, 8],
  ];
  return (
    <svg
      viewBox="0 0 15 12"
      width={15 * px}
      height={12 * px}
      shapeRendering="crispEdges"
      aria-hidden
      className="trophy"
    >
      <g fill="currentColor">
        {cup.map(([x, y, w, h]) => (
          <rect key={`${x},${y}`} x={x} y={y} width={w} height={h} />
        ))}
      </g>
      {/* the shine is a hole in the bowl */}
      <rect x={5} y={3} width={1} height={2} className="trophy-shine" />
      {sparkle &&
        sparkles.map(([x, y], i) => (
          <rect
            key={i}
            x={x}
            y={y}
            width={1}
            height={1}
            fill="currentColor"
            className="wave"
            style={{ animationDelay: `${i * 0.3}s` }}
          />
        ))}
    </svg>
  );
}

/** Hero badge: both wins at a glance, and a jump to the announcements. */
export function WinsBadge() {
  return (
    <a
      href="#wins"
      className="wins-badge group flex w-fit max-w-full items-stretch border-4 border-px bg-lcd shadow-[4px_4px_0_0_var(--color-px)]"
      aria-label="Grand winner of Hack-Nation's 7th Global AI Hackathon, and Health Track winner of the World Bank Group Small AI for Development Hackathon Challenge. See the announcements."
    >
      <span className="flex shrink-0 items-center bg-px px-3 text-lcd">
        <Trophy px={3} />
      </span>
      <span className="flex min-w-0 flex-col justify-center gap-1 px-3 py-2 font-mono text-[12px] leading-snug md:text-[13px]">
        <span>
          <b className="font-semibold">GRAND WINNER</b> · Hack-Nation 7th Global AI Hackathon
        </span>
        <span>
          <b className="font-semibold">HEALTH TRACK WINNER</b> · World Bank Group Small AI for Development
        </span>
      </span>
      <span className="wins-badge-arrow hidden items-center border-l-4 border-px px-3 font-mono sm:flex" aria-hidden>
        ▼
      </span>
    </a>
  );
}

export function Wins() {
  return (
    <Screen id="wins" title="THE WINS" signal={4} data={false}>
      <div className="mx-auto grid grid-cols-1 w-full max-w-[1280px] items-center gap-10 lg:grid-cols-[minmax(0,1fr)_512px] lg:gap-14">
        <div className="min-w-0">
          <div className="mb-5 flex items-center gap-4 font-mono text-sm font-medium">
            <span className="bg-px px-2 py-1 text-lcd">2</span>
            <span>wins, October 2026</span>
          </div>
          <h2 className="text-[36px] leading-[1.05] font-bold tracking-tight md:text-[60px]">Two wins, one weekend.</h2>
          <p className="mt-4 max-w-[620px] text-lg leading-snug md:text-2xl">
            Vitamin Bob was named grand winner of the 7th Global AI Hackathon, and won the Health Track of the World
            Bank Group’s challenge. Next stop: Seoul, for the Global AI &amp; Digital Summit.
          </p>

          <ol className="mt-8 flex flex-col gap-5">
            {WINS.map((w, i) => (
              <li key={w.org}>
                <a
                  href={w.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="social award-card px-box flex flex-col bg-lcd"
                  aria-label={`${w.title}, ${w.org.toLowerCase()} ${w.event}: read the post on LinkedIn (opens in a new tab)`}
                >
                  <span className="award-head flex items-center justify-between gap-3 bg-px px-4 py-2 font-mono text-[12px] font-medium tracking-wider text-lcd md:text-[13px]">
                    <span className="truncate">
                      {i + 1} · {w.org}
                    </span>
                    <Trophy px={2} sparkle={false} />
                  </span>
                  <span className="flex items-center gap-4 px-4 py-4">
                    <span className="min-w-0 flex-1">
                      <span className="block text-[26px] leading-none font-bold tracking-tight md:text-[32px]">
                        {w.title}
                      </span>
                      <span className="mt-2 block text-lg leading-snug">{w.event}</span>
                      <span className="mt-1 block font-mono text-[12px] leading-relaxed opacity-80">{w.detail}</span>
                    </span>
                  </span>
                  <span className="flex items-center gap-3 border-t-2 border-dotted border-current px-4 py-2 font-mono text-[13px] font-medium">
                    <LogoChip src="/images/logos/linkedin-icon.svg" alt="" />
                    <span className="flex-1">Read the post</span>
                    <FlyArrow />
                  </span>
                </a>
              </li>
            ))}
          </ol>
        </div>

        <div className="flex min-w-0 justify-center">
          <LinkedInEmbed
            src={WB_EMBED}
            href={WINS[1].href}
            head="WORLD BANK GROUP · POST"
            title="World Bank Group: Digital & AI on LinkedIn: meet the winners of the Small AI for Development Hackathon Challenge"
          />
        </div>
      </div>
    </Screen>
  );
}
