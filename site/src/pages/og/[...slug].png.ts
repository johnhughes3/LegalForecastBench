import type { APIRoute, GetStaticPaths } from "astro";
import { publishedFindings } from "../../data/findings";
import { ranks, sortedBy } from "../../data/metrics";
import { snapshot } from "../../data/results";
import { type CardSpec, renderCard } from "../../og/card";
import { SECTION_CARDS, type SectionKey } from "../../og/routes";

// Built once per static path at build time; Vercel serves the PNGs from dist/.
const { cohort } = snapshot;
const cohortLine = `${cohort.case_count} federal cases · ${cohort.unit_count} claim-defendant units`;
const brier = (value: number): string => value.toFixed(4);
/** "GPT-6 Sol (agentic; high reasoning)" -> ["GPT-6 Sol", "agentic; high reasoning"]. */
function splitName(display: string): [string, string | null] {
	const match = /^(.*?)\s*\((.+)\)$/.exec(display);
	return match?.[1] && match[2] ? [match[1], match[2]] : [display, null];
}
const kindLabels = { report: "Report", note: "Note", critique: "Critique" };

function sectionCard(key: SectionKey): CardSpec {
	const card = SECTION_CARDS[key];
	if (key !== "home") return { kind: "section", ...card, cohort: cohortLine };
	// GPT-4.1 is a reference baseline, not a frontier contender, so the home
	// card's leaderboard omits it (as the site's cost chart does).
	const microRanks = ranks(snapshot, "micro_brier");
	const leaders = sortedBy(snapshot, "micro_brier")
		.filter((m) => m.slug !== "gpt-4-1")
		.slice(0, 5)
		.map((m) => ({
			rank: microRanks.get(m.slug) ?? 0,
			name: splitName(m.display_name)[0],
			value: brier(m.micro_brier),
		}));
	return { kind: "home", title: card.title, cohort: cohortLine, leaders };
}

export const getStaticPaths = (async () => {
	const total = snapshot.models.length;
	const microRanks = ranks(snapshot, "micro_brier");
	const sections = (Object.keys(SECTION_CARDS) as SectionKey[]).map((key) => ({
		params: { slug: key },
		props: { spec: sectionCard(key) },
	}));
	const models = snapshot.models.map((m) => {
		const [name, qualifier] = splitName(m.display_name);
		return {
			params: { slug: `models/${m.slug}` },
			props: {
				spec: {
					kind: "model",
					name,
					qualifier,
					provider: m.provider,
					brier: brier(m.micro_brier),
					rank: microRanks.get(m.slug) ?? total,
					total,
					cohort: cohortLine,
				} satisfies CardSpec,
			},
		};
	});
	const findings = (await publishedFindings()).map((entry) => ({
		params: { slug: `findings/${entry.id}` },
		props: {
			spec: {
				kind: "finding",
				kindLabel: kindLabels[entry.data.kind],
				title: entry.data.title,
				cohort: cohortLine,
			} satisfies CardSpec,
		},
	}));
	return [...sections, ...models, ...findings];
}) satisfies GetStaticPaths;

export const GET: APIRoute = async ({ props, site }) => {
	const { spec } = props as { spec: CardSpec };
	const host = (site?.hostname ?? "legalforecastbench.org").replace(
		/^www\./,
		"",
	);
	const png = await renderCard(spec, host);
	return new Response(png, { headers: { "Content-Type": "image/png" } });
};
