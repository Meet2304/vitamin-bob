import Image from "next/image";
import { FlyArrow, asset } from "./Links";
import { Screen } from "./Phone";
import { rise } from "./rise";
import { Chip, Kicker } from "./Problem";

/**
 * Recognition: the summit talk (a badge in the hero, and a programme card here) and the two wins, each linking to
 * its LinkedIn post. Wording follows the two posts and the invitation.
 */
export const SUMMIT = {
  event: "Global AI & Digital Summit",
  host: "World Bank Group",
  partners: "with Korea’s Ministry of Finance and Economy and Ministry of Science and ICT",
  session: "Benefiting Billions: Scaling AI for Healthier Lives",
  when: "21 October 2026, 10:30",
  where: "Grand Hyatt Seoul, Korea",
};

export const WINS = [
  {
    org: "WORLD BANK GROUP",
    name: "World Bank Group",
    logo: { src: "/images/logos/world-bank-group.png", w: 640, h: 126 },
    title: "Health Track winner",
    event: "Small AI for Development Hackathon Challenge",
    detail: "AI that lowers barriers to care by understanding patients in their own language.",
    href: "https://www.linkedin.com/feed/update/urn:li:ugcPost:7516077076857389056/",
  },
  {
    org: "HACK-NATION",
    name: "Hack-Nation",
    logo: { src: "/images/logos/hack-nation.png", w: 233, h: 90 },
    title: "Grand winner",
    event: "7th Global AI Hackathon",
    detail: "24 hours, 3,000+ builders, one grand winner.",
    href: "https://www.linkedin.com/posts/hack-nation_hacknation-globalaihackathon-buildinpublic-activity-7515871527326699520-EMsF",
  },
];

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

/**
 * The hero's bottom strip: the two awarding organisations' logos, then the summit talk, all leading to the
 * recognition screen. Sizes are inline so the logos can never render at their full intrinsic size.
 */
export function Recognition() {
  return (
    <a
      href="#recognition"
      className="recognition-strip group mt-[clamp(8px,3svh,32px)] flex flex-wrap items-center gap-x-6 gap-y-3 border-t-4 border-px pt-[clamp(12px,2.4svh,22px)]"
      aria-label={`Winner of the ${WINS[0].name} ${WINS[0].event} and the ${WINS[1].name} ${WINS[1].event}; ignite talk at the ${SUMMIT.host} ${SUMMIT.event}, Seoul. See recognition.`}
    >
      <span className="flex items-center gap-3">
        <span className="flex items-center gap-2 font-mono text-[12px] font-semibold tracking-wider whitespace-nowrap md:text-[13px]">
          <Trophy px={2} sparkle={false} />
          2× WINNER
        </span>
        {WINS.map((w) => (
          <span
            key={w.org}
            className="award-logo flex items-center border-2 border-px bg-paper"
            style={{ height: "clamp(34px, 5.6svh, 52px)", padding: "0 clamp(8px, 1.2vw, 14px)" }}
          >
            <Image
              src={asset(w.logo.src)}
              alt=""
              width={w.logo.w}
              height={w.logo.h}
              unoptimized
              style={{ height: "56%", width: "auto" }}
            />
          </span>
        ))}
      </span>
      <span className="flex min-w-0 items-center gap-3 font-mono text-[12px] leading-snug drop-2 md:text-[13px]">
        <span className="flex shrink-0 items-center gap-2 bg-accent px-2 py-1 font-semibold tracking-wider text-lcd">
          <span className="on-air h-2 w-2 bg-lcd" aria-hidden />
          IGNITE TALK
        </span>
        <span className="min-w-0">
          <b className="font-semibold">{SUMMIT.event}</b>
          <span className="hidden lg:inline"> · {SUMMIT.host}</span> · Seoul, Oct 2026
        </span>
        <span className="recognition-arrow hidden md:inline" aria-hidden>
          ↓
        </span>
      </span>
    </a>
  );
}

/**
 * The winner's seal, stuck on the corner of the hero phone: both wins written round a pixel trophy, turning
 * slowly. Pointing at it stops the turn and lifts it; it leads to the recognition screen.
 */
export function WinnerSeal() {
  const ring = "2× WINNER · WORLD BANK GROUP · HACK-NATION · ";
  return (
    <a
      href="#recognition"
      className="winner-seal"
      aria-label={`Winner: ${WINS[0].title}, ${WINS[0].name}; ${WINS[1].title}, ${WINS[1].name}. See recognition.`}
    >
      <svg viewBox="0 0 100 100" aria-hidden>
        <defs>
          <path id="seal-ring" d="M50,50 m-38,0 a38,38 0 1,1 76,0 a38,38 0 1,1 -76,0" />
        </defs>
        <circle cx={50} cy={50} r={48} fill="var(--color-accent)" stroke="var(--color-px)" strokeWidth={3} />
        <circle cx={50} cy={50} r={26} fill="var(--color-lcd)" stroke="var(--color-px)" strokeWidth={2.5} />
        <g className="winner-seal-ring">
          <text
            fill="var(--color-lcd)"
            fontSize={8.4}
            fontWeight={600}
            letterSpacing={0.4}
            style={{ fontFamily: "var(--font-mono)" }}
          >
            <textPath href="#seal-ring" textLength={237} lengthAdjust="spacing">
              {ring}
            </textPath>
          </text>
        </g>
      </svg>
      <span className="winner-seal-cup">
        <Trophy px={3.6} />
      </span>
    </a>
  );
}

/** The summit talk as a programme card: ON AIR lamp, session, time and place. */
function SummitCard() {
  const rows: [string, string][] = [
    ["SESSION", SUMMIT.session],
    ["WHEN", SUMMIT.when],
    ["WHERE", SUMMIT.where],
  ];
  return (
    <div className="lift border-4 border-px bg-lcd shadow-[4px_4px_0_0_var(--color-accent)]">
      <div className="flex items-center justify-between gap-3 bg-accent px-4 py-2 font-mono text-[12px] font-medium tracking-wider text-lcd md:text-[13px]">
        <span className="truncate">IGNITE TALK · SEOUL</span>
        <span className="flex shrink-0 items-center gap-2">
          <span className="on-air h-2.5 w-2.5 bg-lcd" aria-hidden />
          ON AIR
        </span>
      </div>
      <div className="hidden items-center gap-3 border-b-4 border-px bg-paper px-4 py-2 md:flex">
        <span className="font-mono text-[11px] font-medium tracking-wider text-px">HOSTED BY</span>
        <Image
          src={asset(WINS[0].logo.src)}
          alt={SUMMIT.host}
          width={WINS[0].logo.w}
          height={WINS[0].logo.h}
          unoptimized
          className="h-[clamp(18px,3svh,26px)] w-auto"
        />
      </div>
      <div className="p-[clamp(14px,2.6svh,24px)]">
        <div className="t-h3">{SUMMIT.event}</div>
        <div className="t-body mt-1 hidden md:block">
          The {SUMMIT.host}’s flagship conference on AI for development, {SUMMIT.partners}.
        </div>
        <dl className="drop-4 mt-[clamp(10px,2svh,18px)] grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 border-t-2 border-dotted border-px pt-[clamp(10px,2svh,16px)]">
          {rows.map(([k, v]) => (
            <div key={k} className={k === "WHERE" ? "drop-3 contents" : "contents"}>
              <dt className="pt-[3px] font-mono text-[11px] font-medium md:text-[12px]">{k}</dt>
              <dd className="t-body">{v}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}

export function Wins() {
  return (
    <Screen id="recognition" title="RECOGNITION" signal={4} data={false}>
      <div className="mx-auto grid w-full max-w-[1280px] grid-cols-1 items-center gap-[clamp(16px,3.6svh,40px)] lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-14">
        <div className="min-w-0">
          <Kicker>
            <Chip>SEOUL</Chip>
            <span>October 2026</span>
          </Kicker>
          <h2 className="rise t-h2" style={rise(1)}>
            From a hackathon to the <span className="text-accent">{SUMMIT.host}</span> stage.
          </h2>
          <p className="rise t-lead mt-[clamp(10px,2svh,20px)] max-w-[560px] drop-1" style={rise(2)}>
            One weekend brought two wins: the {SUMMIT.host}’s Health Track and Hack-Nation’s grand prize. Now we are
            taking Vitamin Bob to Seoul, as an ignite talk at the {SUMMIT.event}.
          </p>

          <ol className="mt-[clamp(14px,3svh,32px)] grid grid-cols-2 gap-[clamp(10px,1.6vw,20px)]">
            {WINS.map((w, i) => (
              <li key={w.org} className="rise flex" style={rise(i + 3)}>
                <a
                  href={w.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="plaque award-card px-box flex w-full flex-col bg-lcd"
                  aria-label={`${w.title}, ${w.name} ${w.event}: read the post on LinkedIn (opens in a new tab)`}
                >
                  <span className="flex h-[clamp(60px,11svh,108px)] items-center justify-center border-b-4 border-px bg-paper px-[clamp(12px,1.6vw,24px)]">
                    <Image
                      src={asset(w.logo.src)}
                      alt={w.name}
                      width={w.logo.w}
                      height={w.logo.h}
                      unoptimized
                      className="plaque-logo max-h-[58%] w-auto max-w-full object-contain"
                    />
                  </span>
                  <span className="flex flex-1 items-start gap-2 px-3 py-2.5 md:px-4">
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-2 text-[15px] leading-tight font-bold md:text-[19px]">
                        <span className="hidden shrink-0 sm:inline">
                          <Trophy px={1.5} sparkle={false} />
                        </span>
                        {w.title}
                      </span>
                      <span className="mt-1 hidden font-mono text-[10.5px] leading-snug sm:block md:text-[12px]">
                        {w.event}
                      </span>
                    </span>
                    <FlyArrow />
                  </span>
                </a>
              </li>
            ))}
          </ol>
        </div>

        <div className="rise min-w-0" style={rise(3)}>
          <SummitCard />
        </div>
      </div>
    </Screen>
  );
}
