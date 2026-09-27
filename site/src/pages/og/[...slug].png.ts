import type { APIRoute, GetStaticPaths } from "astro";
import { publishedFindings } from "../../data/findings";
import { ranks, sortedBy } from "../../data/metrics";
import { primarySnapshot, REFERENCE_SLUGS, snapshot } from "../../data/results";
import { type CardSpec, renderCard } from "../../og/card";
import { SECTION_CARDS, type SectionKey } from "../../og/routes";

// Built once per static path at build time; Vercel serves the PNGs from dist/.
const { cohort } = snapshot;
const cohortLine = `${cohort.case_count} federal cases · ${cohort.unit_count} claim-defendant units`;
const brier = (value: number): string => value.toFixed(4);
const kindLabels = { report: "Report", note: "Note", critique: "Critique" };

function sectionCard(key: SectionKey): CardSpec {
	const card = SECTION_CARDS[key];
	if (key !== "home") return { kind: "section", ...card, cohort: cohortLine };
	// Reference configurations (GPT-4.1) are not ranked with current models.
	const microRanks = ranks(primarySnapshot, "micro_brier");
	const leaders = sortedBy(primarySnapshot, "micro_brier")
		.slice(0, 5)
		.map((m) => ({
			rank: microRanks.get(m.slug) ?? 0,
			name: m.display_name,
			value: brier(m.micro_brier),
		}));
	return { kind: "home", title: card.title, cohort: cohortLine, leaders };
}

export const getStaticPaths = (async () => {
	// Same ranking as the model pages: references are shown but not ranked.
	const total = primarySnapshot.models.length;
	const microRanks = ranks(primarySnapshot, "micro_brier");
	const sections = (Object.keys(SECTION_CARDS) as SectionKey[]).map((key) => ({
		params: { slug: key },
		props: { spec: sectionCard(key) },
	}));
	const models = snapshot.models.map((m) => ({
		params: { slug: `models/${m.slug}` },
		props: {
			spec: {
				kind: "model",
				name: m.display_name,
				provider: m.provider,
				microBrier: brier(m.micro_brier),
				equalCaseBrier: brier(m.equal_case_brier),
				rank: REFERENCE_SLUGS.has(m.slug)
					? null
					: (microRanks.get(m.slug) ?? null),
				total,
				cohort: cohortLine,
			} satisfies CardSpec,
		},
	}));
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
