import { readFile } from "node:fs/promises";
import { parseSiteExport } from "../src/data/site-export.js";

const path = process.argv[2];
if (!path || process.argv.length !== 3) {
	throw new Error("Usage: pnpm contract:validate <site-export.json>");
}
const value: unknown = JSON.parse(await readFile(path, "utf8"));
parseSiteExport(value);
console.log("Site export matches the published contract.");
