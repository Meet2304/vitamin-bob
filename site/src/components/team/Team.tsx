"use client";

import { Check, Copy } from "lucide";
import { MorphIcon } from "morphicons/react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore, type CSSProperties, type ReactNode } from "react";
import { asset, FlyArrow, LogoChip } from "../lcd/Links";
import { Screen } from "../lcd/Phone";
import { MEMBERS, linkedinHandle, siteHandle, xHandle, type Member } from "./members";

/**
 * The team, as the phone's contacts: a group call in the hero, then one speed-dial card per person.
 * Photos are dithered LCD pixels until you hover (or tap) them, then the colour scans in line by line.
 * Press 1–4 to dial someone (their card rings), 0 to go back to the story.
 */

const REDUCED = "(prefers-reduced-motion: reduce)";

function useReducedMotion() {
  return useSyncExternalStore(
    (on) => {
      const mq = window.matchMedia(REDUCED);
      mq.addEventListener("change", on);
      return () => mq.removeEventListener("change", on);
    },
    () => window.matchMedia(REDUCED).matches,
    () => false,
  );
}

/** Scroll to someone's card and make it ring. */
function dial(slug: string) {
  const el = document.getElementById(slug);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.remove("ringing");
  void el.offsetWidth; // restart the animation if it is already ringing
  el.classList.add("ringing");
  el.querySelector<HTMLElement>(".photo")?.focus({ preventScroll: true });
}

function useSpeedDial() {
  const router = useRouter();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const t = e.target as HTMLElement;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      if (e.key === "0") return router.push("/");
      const m = MEMBERS[Number(e.key) - 1];
      if (m) dial(m.slug);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router]);
}

/* ---------- Hero: a group call with the four of us ---------- */

function useElapsed() {
  const [s, setS] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setS((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function GroupCall() {
  const reduced = useReducedMotion();
  const elapsed = useElapsed();
  const [speaker, setSpeaker] = useState(0);
  const [held, setHeld] = useState<number | null>(null);
  useEffect(() => {
    if (reduced || held !== null) return;
    const id = setInterval(() => setSpeaker((n) => (n + 1) % MEMBERS.length), 1800);
    return () => clearInterval(id);
  }, [reduced, held]);
  const live = held ?? speaker;

  return (
    <div className="px-box w-full max-w-[420px] bg-lcd">
      <div className="flex items-center justify-between bg-px px-4 py-2 font-mono text-[13px] font-medium tracking-wider text-lcd">
        <span>GROUP CALL · {MEMBERS.length}</span>
        <span aria-label="call time">{elapsed}</span>
      </div>
      <div className="grid grid-cols-4 gap-2 bg-lcd-2/60 p-3 sm:grid-cols-2 sm:gap-3 sm:p-4">
        {MEMBERS.map((m, i) => (
          <button
            key={m.slug}
            type="button"
            onMouseEnter={() => setHeld(i)}
            onMouseLeave={() => setHeld(null)}
            onFocus={() => setHeld(i)}
            onBlur={() => setHeld(null)}
            onClick={() => dial(m.slug)}
            className={`tile relative block text-left ${i === live ? "speaking" : ""}`}
            aria-label={`Dial ${m.name}`}
          >
            <Image
              src={asset(`/images/team/${m.slug}-lcd.png`)}
              alt=""
              width={200}
              height={250}
              unoptimized
              priority
              className="lcd-photo block aspect-[4/5] h-auto w-full border-4 border-px"
            />
            <span className="tile-name absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 px-1 py-0.5 font-mono text-[10px] font-medium sm:px-2 sm:py-1 sm:text-[12px]">
              <span className="truncate">{m.name}</span>
              <span className="hidden h-3 items-end gap-[2px] sm:flex" aria-hidden>
                {[0, 1, 2, 3].map((b) => (
                  <span
                    key={b}
                    className="eq-mini w-[3px] bg-current"
                    style={{ height: `${40 + b * 20}%`, animationDelay: `${b * 0.15}s` }}
                  />
                ))}
              </span>
            </span>
          </button>
        ))}
      </div>
      <div className="flex items-center gap-2 border-t-4 border-px px-4 py-2 font-mono text-[13px]" aria-live="polite">
        {/* on phones the tiles are too small for voice bars, so the line below carries them */}
        <span aria-hidden>◀))</span>
        <span>
          speaking: <b>{MEMBERS[live].name}</b>
        </span>
        <span className="ml-auto flex h-3 items-end gap-[2px] sm:hidden" aria-hidden>
          {[0, 1, 2, 3].map((b) => (
            <span
              key={b}
              className="eq w-[3px] bg-current"
              style={{ height: `${40 + b * 20}%`, animationDelay: `${b * 0.15}s` }}
            />
          ))}
        </span>
      </div>
      <div className="grid grid-cols-2 border-t-4 border-px font-mono text-[13px] font-medium tracking-wider">
        <a href="#contacts" className="border-r-4 border-px py-2.5 text-center hover:bg-px hover:text-lcd sm:py-3">
          CONTACTS
        </a>
        <a
          href={`mailto:${MEMBERS.map((m) => m.email).join(",")}`}
          className="bg-px py-2.5 text-center text-lcd hover:bg-px-2 sm:py-3"
        >
          EMAIL ALL 4
        </a>
      </div>
    </div>
  );
}

export function TeamHero() {
  useSpeedDial();
  return (
    <Screen id="team" title="CONTACTS">
      <div className="mx-auto grid w-full max-w-[1280px] items-center gap-8 md:grid-cols-[1.25fr_1fr] md:gap-14">
        <div className="flex flex-col gap-5 md:gap-8">
          <div className="flex items-center gap-4 font-mono text-sm font-medium">
            <span className="bg-px px-2 py-1 text-lcd">{MEMBERS.length}</span>
            <span>contacts saved</span>
          </div>
          <h1 className="text-[40px] leading-[1.02] font-bold tracking-tight md:text-[76px]">
            The people behind Bob<span className="cursor">_</span>
          </h1>
          <p className="max-w-[600px] text-lg leading-snug md:text-2xl">
            We built Vitamin Bob for the Hack-Nation × World Bank <i>Small AI for Development</i> hackathon, health
            track, October 2026. Bob always calls back. So do we.
          </p>
          <nav aria-label="Speed dial" className="hidden flex-col gap-3 md:flex">
            {MEMBERS.map((m, i) => (
              <a
                key={m.slug}
                href={`#${m.slug}`}
                onClick={(e) => {
                  e.preventDefault();
                  dial(m.slug);
                }}
                className="group flex items-center gap-4 text-xl md:text-2xl"
              >
                <span className="px-box flex h-11 w-11 shrink-0 items-center justify-center font-mono text-lg font-semibold group-hover:bg-px group-hover:text-lcd">
                  {i + 1}
                </span>
                <span>
                  Press {i + 1} for <span className="font-semibold">{m.name}</span>
                </span>
              </a>
            ))}
          </nav>
        </div>
        <div className="flex justify-center">
          <GroupCall />
        </div>
      </div>
    </Screen>
  );
}

/* ---------- Contacts: one speed-dial card per person ---------- */

/** Copy to the clipboard, with the old-fashioned fallback for pages that are not a secure context. */
async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;opacity:0;pointer-events:none";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  }
}

const BURST = [
  [-26, -18],
  [26, -18],
  [-34, 2],
  [34, 2],
  [-18, 22],
  [18, 22],
  [0, -30],
  [0, 28],
];

function CopyEmail({ member }: { member: Member }) {
  const reduced = useReducedMotion();
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const [shot, setShot] = useState(0); // remounts the bubble and burst so they replay on every click
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);

  const onCopy = async () => {
    const ok = await copyText(member.email);
    setState(ok ? "copied" : "failed");
    setShot((n) => n + 1);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setState("idle"), 1900);
  };

  return (
    <span className="relative shrink-0">
      <button
        type="button"
        onClick={onCopy}
        data-state={state}
        className="copy-btn flex h-11 w-10 items-center justify-center border-l-4 border-px sm:w-11"
        aria-label={state === "copied" ? `${member.name}'s email copied` : `Copy ${member.name}'s email`}
      >
        <MorphIcon
          icon={state === "copied" ? Check : Copy}
          spring="bouncy"
          size={20}
          strokeWidth={state === "copied" ? 3 : 2.25}
          reducedMotion="user"
        />
      </button>
      {state !== "idle" && (
        <span key={shot} aria-hidden>
          <span className="copied-bubble pointer-events-none absolute right-0 bottom-[calc(100%+10px)] z-10 font-mono text-[12px] font-semibold whitespace-nowrap">
            {state === "copied" ? "COPIED ✓" : "PRESS CTRL+C"}
          </span>
          {state === "copied" &&
            !reduced &&
            BURST.map(([dx, dy], i) => (
              <span
                key={i}
                className="burst pointer-events-none absolute top-1/2 left-1/2 z-10 h-[5px] w-[5px]"
                style={{ "--dx": `${dx}px`, "--dy": `${dy}px`, animationDelay: `${(i % 3) * 30}ms` } as CSSProperties}
              />
            ))}
        </span>
      )}
      <span className="sr-only" aria-live="polite">
        {state === "copied" ? "Email copied" : state === "failed" ? "Could not copy the email" : ""}
      </span>
    </span>
  );
}

function SocialRow({
  href,
  logo,
  label,
  text,
  external = true,
  children,
}: {
  href: string;
  logo: ReactNode;
  label: string;
  text: string;
  external?: boolean;
  children?: ReactNode;
}) {
  return (
    <li className="flex items-stretch border-b-2 border-dotted border-px-2 last:border-0">
      <a
        href={href}
        {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
        aria-label={label}
        className="social flex min-w-0 flex-1 items-center gap-2 px-2 py-1.5 sm:gap-3 sm:px-3"
      >
        {logo}
        <span className="min-w-0 flex-1 truncate font-mono text-[12px] font-medium sm:text-[13px]" title={text}>
          {text}
          <span className="social-cursor cursor">_</span>
        </span>
        {external && <FlyArrow />}
      </a>
      {children}
    </li>
  );
}

function ContactCard({ member, n }: { member: Member; n: number }) {
  const [colour, setColour] = useState(false);
  return (
    <article
      id={member.slug}
      className="contact-card px-box flex min-w-0 flex-col bg-lcd"
      style={{ "--i": n } as CSSProperties}
    >
      <div className="flex items-center justify-between bg-px px-4 py-2 font-mono text-[13px] font-medium tracking-wider text-lcd">
        <span>SPEED DIAL {n}</span>
        <span>
          {n}/{MEMBERS.length}
        </span>
      </div>

      {/* phones: photo | name, then the rows across the card. sm and up: photo down the left, name and rows beside it */}
      <div className="grid grid-cols-[104px_minmax(0,1fr)] sm:grid-cols-[220px_minmax(0,1fr)] sm:grid-rows-[1fr_auto]">
        <button
          type="button"
          className="photo group/photo relative block aspect-[4/5] w-full overflow-hidden border-r-4 border-b-4 border-px sm:row-span-2 sm:border-b-0"
          aria-pressed={colour}
          aria-label={`Show ${member.name}'s photo in colour`}
          onClick={() => setColour((c) => !c)}
        >
          <Image
            src={asset(`/images/team/${member.slug}-lcd.png`)}
            alt={`${member.name}, in LCD pixels`}
            width={200}
            height={250}
            unoptimized
            className="lcd-photo absolute inset-0 h-full w-full object-cover"
          />
          <Image
            src={asset(`/images/team/${member.slug}.webp`)}
            alt={member.name}
            width={640}
            height={800}
            unoptimized
            className="photo-colour absolute inset-0 h-full w-full object-cover"
          />
          <span className="scanline absolute inset-x-0 h-[6px] bg-px" aria-hidden />
          <span className="photo-tag absolute bottom-3 left-3 hidden bg-px px-2 py-0.5 font-mono text-[11px] font-medium tracking-wider text-lcd sm:inline">
            <span className="tag-lcd">
              <span className="hover-word">HOVER</span>
              <span className="tap-word">TAP</span> TO SAY HI
            </span>
            <span className="tag-colour">HI, I’M {member.name.toUpperCase()}</span>
          </span>
        </button>

        <div className="flex min-w-0 flex-col justify-center gap-2 border-b-4 border-px p-4 sm:justify-start sm:border-b-0">
          <h3 className="truncate pb-[0.12em] text-[24px] leading-[1.1] min-[380px]:text-[28px] font-bold tracking-tight sm:text-[34px]">
            {member.name}
          </h3>
          <span className="font-mono text-[11px] font-medium sm:hidden">tap for colour ▸</span>
        </div>

        <div className="col-span-2 min-w-0 p-3 sm:col-span-1 sm:p-4 sm:pt-0">
          <ul className="border-4 border-px">
            <SocialRow
              href={`mailto:${member.email}`}
              external={false}
              label={`Email ${member.name} at ${member.email}`}
              text={member.email}
              logo={<LogoChip src="/images/logos/google-gmail.svg" alt="" />}
            >
              <CopyEmail member={member} />
            </SocialRow>
            {member.website && (
              <SocialRow
                href={member.website}
                label={`${member.name}'s website, ${siteHandle(member.website)} (opens in a new tab)`}
                text={siteHandle(member.website)}
                logo={<LogoChip src={member.websiteLogo ?? "/images/logos/globe.svg"} alt="" />}
              />
            )}
            <SocialRow
              href={member.linkedin}
              label={`${member.name} on LinkedIn (opens in a new tab)`}
              text={linkedinHandle(member.linkedin)}
              logo={<LogoChip src="/images/logos/linkedin-icon.svg" alt="" />}
            />
            <SocialRow
              href={member.x}
              label={`${member.name} on X (opens in a new tab)`}
              text={xHandle(member.x)}
              logo={<LogoChip src="/images/logos/x.svg" alt="" />}
            />
          </ul>
        </div>
      </div>
    </article>
  );
}

/** Cards boot up one after another the first time they scroll into view. */
function useSeen<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setSeen(true);
          io.disconnect();
        }
      },
      { threshold: 0.15 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return [ref, seen] as const;
}

export function Contacts() {
  const [ref, seen] = useSeen<HTMLDivElement>();
  return (
    <Screen id="contacts" title="SPEED DIAL">
      <div className="mx-auto w-full max-w-[1280px]">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <h2 className="text-[36px] leading-[1.05] font-bold tracking-tight md:text-[60px]">Say hello.</h2>
          </div>
          <div className="hidden font-mono text-[13px] font-medium sm:block">press 1–4 to speed dial</div>
        </div>
        <div
          ref={ref}
          data-seen={seen ? "" : undefined}
          className="contacts-grid mt-6 grid grid-cols-1 gap-6 md:mt-10 md:gap-8 xl:grid-cols-2"
        >
          {MEMBERS.map((m, i) => (
            <ContactCard key={m.slug} member={m} n={i + 1} />
          ))}
        </div>
      </div>
    </Screen>
  );
}
