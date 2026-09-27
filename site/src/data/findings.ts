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
	return entries.sort((a, b) => b.data.date.valueOf() - a.data.date.valueOf());
}
