import { parseSnapshot } from "./snapshot.js";
import beta from "./snapshots/beta-2026-09-18.json" with { type: "json" };

/** The results snapshot the site currently presents. Validated at build time. */
export const snapshot = parseSnapshot(structuredClone(beta));
