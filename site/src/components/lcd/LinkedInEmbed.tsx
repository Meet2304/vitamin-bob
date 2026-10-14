"use client";

import { useState } from "react";

/**
 * A LinkedIn post embed shown on a little handset. The frame only loads once it nears the viewport
 * (loading="lazy"); until then, and while it loads, the screen shows an LCD placeholder. The link to the
 * post is always on the soft key, for when the embed is blocked (privacy extensions, Bob's offline copy).
 */
export function LinkedInEmbed({ src, href, title, head }: { src: string; href: string; title: string; head: string }) {
  const [ready, setReady] = useState(false);
  return (
    <div className="px-box w-full max-w-[512px] bg-lcd">
      <div className="flex items-center justify-between gap-3 bg-px px-4 py-2 font-mono text-[13px] font-medium tracking-wider text-lcd">
        <span className="truncate">{head}</span>
        <span className="shrink-0">LINKEDIN</span>
      </div>
      <div className="relative h-[567px] bg-white">
        {!ready && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-lcd-2 font-mono text-[13px] font-medium">
            <span className="flex h-6 items-end gap-1" aria-hidden>
              {[0, 1, 2, 3, 4].map((b) => (
                <span key={b} className="eq w-2 bg-px" style={{ height: "100%", animationDelay: `${b * 0.12}s` }} />
              ))}
            </span>
            LOADING THE POST…
          </div>
        )}
        <iframe
          src={src}
          title={title}
          loading="lazy"
          allowFullScreen
          onLoad={() => setReady(true)}
          className={`absolute inset-0 block h-full w-full border-0 ${ready ? "" : "opacity-0"}`}
        />
      </div>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="block border-t-4 border-px bg-px py-3 text-center font-mono text-[13px] font-medium tracking-wider text-lcd hover:bg-px-2"
      >
        OPEN ON LINKEDIN ↗
      </a>
    </div>
  );
}
