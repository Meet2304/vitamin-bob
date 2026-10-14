import Image from "next/image";

/**
 * Small pieces shared by link rows (team contacts, award posts). Their hover motion lives in globals.css under
 * `.social`: the row inverts, the logo chip lights up and hops, the arrow flies out.
 */

// Plain <img> paths into public/ are not prefixed by Next, so add the base path (/website in Bob's copy).
const base = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
export const asset = (path: string) => `${base}${path}`;

/** An arrow that flies out top-right on hover while its twin slides in from bottom-left. */
export function FlyArrow() {
  const svg = (cls: string) => (
    <svg
      viewBox="0 0 24 24"
      width={18}
      height={18}
      fill="none"
      stroke="currentColor"
      strokeWidth={2.5}
      strokeLinecap="square"
      className={cls}
      aria-hidden
    >
      <path d="M7 17 17 7M8 7h9v9" />
    </svg>
  );
  return (
    <span className="fly-arrow relative block h-[18px] w-[18px] shrink-0 overflow-hidden">
      {svg("a1 absolute inset-0")}
      {svg("a2 absolute inset-0")}
    </span>
  );
}

export function LogoChip({ src, alt }: { src: string; alt: string }) {
  return (
    <span className="logo-chip flex h-7 w-7 shrink-0 sm:h-8 sm:w-8 items-center justify-center border-2 border-px bg-lcd">
      <Image
        src={asset(src)}
        alt={alt}
        width={18}
        height={18}
        unoptimized
        className="h-[18px] w-[18px] object-contain"
      />
    </span>
  );
}
