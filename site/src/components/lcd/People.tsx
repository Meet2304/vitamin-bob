import Image from "next/image";
import Link from "next/link";
import { MEMBERS } from "../team/members";
import { FlyArrow, asset } from "./Links";
import { Screen } from "./Phone";
import { rise } from "./rise";
import { Chip, Kicker } from "./Problem";

/**
 * The team, on the home page: four LCD portraits that scan into colour on hover (the same effect as the contact
 * cards on /team, from `.contact-card` in globals.css), each linking to that person's LinkedIn, and one call to
 * action to the team page.
 */
export function People() {
  return (
    <Screen id="team" title="THE TEAM" signal={4} data={false}>
      <div className="mx-auto w-full max-w-[1280px]">
        <Kicker>
          <Chip>THE TEAM</Chip>
          <span>Who built it</span>
        </Kicker>
        <div className="flex flex-wrap items-end justify-between gap-x-10 gap-y-3">
          <div>
            <h2 className="rise t-h2" style={rise(1)}>
              Four people built <span className="text-accent">Vitamin Bob.</span>
            </h2>
            <p className="rise t-lead mt-[clamp(8px,1.6svh,16px)] max-w-[620px] drop-2" style={rise(2)}>
              We are graduate students at Carnegie Mellon University, working across policy, data and AI.
            </p>
          </div>
          <Link
            href="/team"
            className="rise cta hidden items-center gap-3 border-4 border-px bg-px px-5 py-3 font-mono text-[14px] font-medium text-lcd shadow-[4px_4px_0_0_var(--color-accent)] md:flex"
            style={rise(3)}
          >
            Meet the team
            <FlyArrow />
          </Link>
        </div>

        <ul className="mt-[clamp(16px,4svh,40px)] grid grid-cols-4 gap-[clamp(8px,1.8vw,24px)]">
          {MEMBERS.map((m, i) => (
            <li key={m.slug} className="rise flex" style={rise(i + 3)}>
              <a
                href={m.linkedin}
                target="_blank"
                rel="noopener noreferrer"
                className="contact-card group flex w-full flex-col border-4 border-px bg-lcd"
                aria-label={`${m.fullName}, ${m.role}: LinkedIn (opens in a new tab)`}
              >
                <span className="relative block aspect-[4/5] overflow-hidden border-b-4 border-px md:aspect-auto md:h-[clamp(130px,30svh,380px)]">
                  <Image
                    src={asset(`/images/team/${m.slug}-lcd.png`)}
                    alt=""
                    width={200}
                    height={250}
                    unoptimized
                    loading="eager"
                    className="lcd-photo absolute inset-0 h-full w-full object-cover object-top"
                  />
                  <Image
                    src={asset(`/images/team/${m.slug}.webp`)}
                    alt=""
                    width={640}
                    height={800}
                    unoptimized
                    loading="eager"
                    className="photo-colour absolute inset-0 h-full w-full object-cover object-top"
                  />
                  <span className="scanline absolute inset-x-0 h-[6px] bg-px" aria-hidden />
                </span>
                <span className="block px-2 py-1.5 md:px-3 md:py-2">
                  <span className="block text-[11px] leading-tight font-bold [overflow-wrap:anywhere] sm:text-[13px] md:text-[clamp(14px,2svh,19px)]">
                    <span className="md:hidden">{m.name}</span>
                    <span className="hidden md:inline">{m.fullName}</span>
                  </span>
                  <span className="mt-0.5 block font-mono text-[10px] leading-tight md:text-[12px]">{m.role}</span>
                </span>
              </a>
            </li>
          ))}
        </ul>

        <Link
          href="/team"
          className="rise mt-5 flex items-center justify-center gap-3 border-4 border-px bg-px px-5 py-3 font-mono text-[14px] font-medium text-lcd md:hidden"
          style={rise(7)}
        >
          Meet the team <span aria-hidden>→</span>
        </Link>
      </div>
    </Screen>
  );
}
