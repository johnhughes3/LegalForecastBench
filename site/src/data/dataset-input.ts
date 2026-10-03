import {
	cpSync,
	existsSync,
	mkdirSync,
	readdirSync,
	readFileSync,
	rmSync,
} from "node:fs";
import { resolve } from "node:path";

/** Optional complete output of `legalforecast site refresh`; checked-in data is the default. */
export const refreshedDataDirectory = process.env.LFB_SITE_DATA_DIR
	? resolve(process.env.LFB_SITE_DATA_DIR)
	: undefined;

export function datasetJson<T>(relative: string, fallback: T): T {
	if (!refreshedDataDirectory) return fallback;
	return JSON.parse(
		readFileSync(resolve(refreshedDataDirectory, relative), "utf8"),
	) as T;
}

export function datasetDownloads(
	directory: string,
	fallback: Record<string, unknown>,
): Record<string, unknown> {
	if (!refreshedDataDirectory) return fallback;
	const root = resolve(refreshedDataDirectory, directory);
	return Object.fromEntries(
		readdirSync(root)
			.filter((name) => /\.jsonl?$/.test(name))
			.map((name) => [name, readFileSync(resolve(root, name), "utf8")]),
	);
}

/** Replace downloadable data, preserving generated HTML pages under /data/. */
export function copyRefreshedDownloads(
	source: string,
	destination: string,
): void {
	if (resolve(source) === resolve(destination))
		throw new Error("Refreshed input must be separate from the build output");
	for (const required of [
		"current.json",
		"sources.json",
		"historical-aggregates.json",
	])
		if (!existsSync(resolve(source, required)))
			throw new Error(`Incomplete refreshed dataset: missing ${required}`);
	const removeDownloads = (directory: string): void => {
		if (!existsSync(directory)) return;
		for (const entry of readdirSync(directory, { withFileTypes: true })) {
			const path = resolve(directory, entry.name);
			if (entry.isDirectory()) removeDownloads(path);
			else if (/\.jsonl?$/.test(entry.name)) rmSync(path);
		}
	};
	removeDownloads(destination);
	const copyDownloads = (input: string, output: string): void => {
		for (const entry of readdirSync(input, { withFileTypes: true })) {
			const from = resolve(input, entry.name);
			const to = resolve(output, entry.name);
			if (entry.isDirectory()) copyDownloads(from, to);
			else if (/\.jsonl?$/.test(entry.name)) {
				mkdirSync(output, { recursive: true });
				cpSync(from, to);
			}
		}
	};
	copyDownloads(source, destination);
}
