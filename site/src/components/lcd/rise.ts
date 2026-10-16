import type { CSSProperties } from "react";

/**
 * Order of a `.rise` piece within its screen: `<h2 className="rise" style={rise(1)}>` comes in second. The motion
 * itself is in globals.css. Kept out of Phone.tsx so server components can call it.
 */
export const rise = (n: number) => ({ "--d": n }) as CSSProperties;
