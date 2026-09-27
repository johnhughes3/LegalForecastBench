import { type CollectionEntry, getCollection } from "astro:content";

/** Drafts appear in dev and preview deployments, never in production. */
export const showDrafts =
	import.meta.env.DEV || process.env.VERCEL_ENV === "preview";

export async function publishedFindings(): Promise<
	CollectionEntry<"findings">[]
> {
	const entries = await getCollection(
		"findings",
		(entry) => showDrafts || !entry.data.draft,
	);
	const kindOrder = { report: 0, note: 1, critique: 2 } as const;
	return entries.sort(
		(a, b) =>
			b.data.date.valueOf() - a.data.date.valueOf() ||
			kindOrder[a.data.kind] - kindOrder[b.data.kind] ||
			a.data.title.localeCompare(b.data.title),
	);
}
