"use client";

import { useEffect, useRef, useState } from "react";
import { asset } from "../lcd/Links";
import { Sprite } from "../lcd/Sprite";

// The booth demo is our teammate's page, kept exactly as designed: public/booth/index.html, shown here in a window
// on the glass. It needs nothing from the internet once loaded (its voice clips are inside).
// It is linked as a folder (/booth/) because Vercel serves exported .html files without their extension, so a
// link ending in .html 404s there; Bob's server serves the folder's index.html too. Only `next dev` needs the file
// name spelled out.
const SRC = asset(process.env.NODE_ENV === "development" ? "/booth/index.html" : "/booth/");

/**
 * The demo page: one screen tall, a window bar in the phone's style (what this is, full screen, open on its own)
 * over the demo itself. Bob waits on the glass until the demo has loaded.
 */
export function BoothDemo() {
  const frame = useRef<HTMLIFrameElement>(null);
  const [ready, setReady] = useState(false);

  // The demo can finish loading before this page hydrates, so its load event is missed: check once on mount.
  useEffect(() => {
    if (
      frame.current?.contentDocument?.readyState === "complete" &&
      frame.current.contentWindow?.location.href !== "about:blank"
    )
      setReady(true);
  }, []);

  const fullScreen = () => {
    const el = frame.current;
    if (el?.requestFullscreen) el.requestFullscreen().catch(() => window.open(SRC, "_blank"));
    else window.open(SRC, "_blank");
  };

  return (
    <section
      id="demo"
      data-screen=""
      data-title="BOOTH DEMO"
      data-signal="0"
      data-data="0"
      data-clock=""
      className="screen flex h-[100svh] flex-col px-3 pt-[60px] pb-3 sm:px-6 sm:pb-5 md:px-12 md:pt-[68px] md:pb-8"
    >
      <h1 className="sr-only">Vitamin Bob booth demo: be Kevin for one minute</h1>
      <div className="demo-window mx-auto flex min-h-0 w-full max-w-[1440px] flex-1 flex-col border-4 border-px">
        <div className="flex items-center gap-3 bg-px py-1.5 pr-1.5 pl-3 font-mono text-[11px] font-medium tracking-wider text-lcd sm:text-[12px]">
          <span className="on-air h-2 w-2 shrink-0 bg-accent-hi" aria-hidden />
          <span className="truncate">
            BOOTH DEMO<span className="hidden sm:inline"> · BE KEVIN FOR ONE MINUTE</span>
          </span>
          <span className="hidden border border-lcd/50 px-1.5 md:inline">RUNS IN YOUR BROWSER</span>
          <span className="ml-auto flex shrink-0 items-center">
            <button type="button" onClick={fullScreen} className="demo-btn cursor-pointer px-2 py-1">
              ⛶ FULL SCREEN
            </button>
            <a
              href={SRC}
              target="_blank"
              rel="noopener noreferrer"
              className="demo-btn hidden px-2 py-1 sm:inline"
              aria-label="Open the demo on its own, in a new tab"
            >
              NEW TAB ↗
            </a>
          </span>
        </div>

        <div className="relative min-h-0 flex-1 bg-[#0E1D19]">
          <iframe
            ref={frame}
            src={SRC}
            title="Vitamin Bob booth demo"
            allow="autoplay; fullscreen; screen-wake-lock"
            allowFullScreen
            onLoad={() => setReady(true)}
            className="absolute inset-0 h-full w-full border-0"
          />
          <div
            className={`demo-boot absolute inset-0 flex flex-col items-center justify-center gap-4 bg-lcd ${ready ? "done" : ""}`}
            aria-hidden={ready}
          >
            <Sprite role="bob" mood="happy" px={6} />
            <p className="font-mono text-[13px] font-medium tracking-wider">
              DIALLING THE DEMO<span className="cursor">_</span>
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
