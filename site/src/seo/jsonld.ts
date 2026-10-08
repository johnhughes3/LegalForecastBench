import {
	AUTHOR,
	authorId,
	LEGALQUANTS,
	LOGO_PATH,
	organizationId,
	REPO,
	SITE_NAME,
	SITE_ORIGIN,
	websiteId,
} from "./identity.js";

/** Schema.org node. Values stay JSON-serializable; nothing is invented. */
export interface JsonLdNode {
	[key: string]: JsonLdValue;
}

export type JsonLdValue =
	| string
	| number
	| boolean
	| null
	| JsonLdNode
	| JsonLdValue[];

export interface Crumb {
	name: string;
	path: string;
}

function node(entries: Record<string, JsonLdValue | undefined>): JsonLdNode {
	const out: JsonLdNode = {};
	for (const [key, value] of Object.entries(entries)) {
		if (value !== undefined) out[key] = value;
	}
	return out;
}

export function organizationNode(site: URL): JsonLdNode {
	return {
		"@type": "Organization",
		"@id": organizationId,
		name: SITE_NAME,
		url: site.href,
		logo: {
			"@type": "ImageObject",
			url: new URL(LOGO_PATH, site).href,
		},
		// The project repository identifies the benchmark; the author's profiles
		// identify the Person node, not this organization.
		sameAs: [REPO],
		contactPoint: {
			"@type": "ContactPoint",
			contactType: "author",
			url: AUTHOR.contact,
		},
	};
}

export function websiteNode(site: URL): JsonLdNode {
	return {
		"@type": "WebSite",
		"@id": websiteId,
		name: SITE_NAME,
		url: site.href,
		inLanguage: "en",
		publisher: { "@id": organizationId },
		creator: { "@id": authorId },
	};
}

export function personNode(): JsonLdNode {
	return {
		"@type": "Person",
		"@id": authorId,
		name: AUTHOR.name,
		alternateName: AUTHOR.alternateName,
		url: AUTHOR.site,
		sameAs: [AUTHOR.github, AUTHOR.linkedin, AUTHOR.x],
		memberOf: {
			"@type": "Organization",
			name: LEGALQUANTS.name,
			url: LEGALQUANTS.url,
		},
	};
}

export function breadcrumbNode(
	canonical: string,
	crumbs: readonly Crumb[],
	site: URL,
): JsonLdNode | undefined {
	if (crumbs.length < 2) return undefined;
	return {
		"@type": "BreadcrumbList",
		"@id": `${canonical}#breadcrumb`,
		itemListElement: crumbs.map((crumb, index) => ({
			"@type": "ListItem",
			position: index + 1,
			name: crumb.name,
			item: new URL(crumb.path, site).href,
		})),
	};
}

export function webPageNode(input: {
	canonical: string;
	title: string;
	description: string;
	image: string;
	breadcrumbId?: string | undefined;
}): JsonLdNode {
	return node({
		"@type": "WebPage",
		"@id": `${input.canonical}#webpage`,
		url: input.canonical,
		name: input.title,
		description: input.description,
		isPartOf: { "@id": websiteId },
		publisher: { "@id": organizationId },
		primaryImageOfPage: { "@type": "ImageObject", url: input.image },
		breadcrumb: input.breadcrumbId ? { "@id": input.breadcrumbId } : undefined,
	});
}

/** Author node: the site person when the byline matches, otherwise the name only. */
export function authorRef(name: string): JsonLdNode {
	if (name === AUTHOR.name) return { "@id": authorId };
	return { "@type": "Person", name };
}

export function scholarlyArticle(input: {
	headline: string;
	description: string;
	url: string;
	authorName: string;
	datePublished?: string | null;
	dateModified?: string | null;
	image?: string;
	pdfUrl?: string;
}): JsonLdNode {
	const modified =
		input.dateModified && input.dateModified !== input.datePublished
			? input.dateModified
			: undefined;
	return node({
		"@type": "ScholarlyArticle",
		"@id": `${input.url}#article`,
		headline: input.headline,
		description: input.description,
		url: input.url,
		author: authorRef(input.authorName),
		publisher: { "@id": organizationId },
		isPartOf: { "@id": websiteId },
		datePublished: input.datePublished ?? undefined,
		dateModified: modified,
		image: input.image,
		inLanguage: "en",
		encoding: input.pdfUrl
			? {
					"@type": "MediaObject",
					contentUrl: input.pdfUrl,
					encodingFormat: "application/pdf",
				}
			: undefined,
	});
}

/** What the downloads report for each model configuration. */
const DATASET_VARIABLES = [
	"Micro Brier score",
	"Equal-case Brier score",
	"Unit accuracy",
	"Estimated standard-rate cost",
];

const DATASET_KEYWORDS = [
	"legal AI benchmark",
	"motion to dismiss",
	"judicial outcome forecasting",
	"federal courts",
	"Brier score",
	"large language model evaluation",
];

export function datasetNode(input: {
	name: string;
	description: string;
	url: string;
	temporalCoverage: string;
	/** Release identifier shown on the data page. */
	version: string;
	dateModified: string;
	/** JSON downloads linked from the data page; the first is the main file. */
	downloads: readonly { name: string; contentUrl: string }[];
}): JsonLdNode {
	return {
		"@type": "Dataset",
		"@id": `${input.url}#dataset`,
		name: input.name,
		description: input.description,
		url: input.url,
		creator: { "@id": authorId },
		publisher: { "@id": organizationId },
		version: input.version,
		dateModified: input.dateModified,
		temporalCoverage: input.temporalCoverage,
		spatialCoverage: "United States",
		keywords: DATASET_KEYWORDS,
		variableMeasured: DATASET_VARIABLES,
		isAccessibleForFree: true,
		license: "https://creativecommons.org/licenses/by/4.0/",
		distribution: input.downloads.map((download) => ({
			"@type": "DataDownload",
			name: download.name,
			encodingFormat: "application/json",
			contentUrl: download.contentUrl,
		})),
	};
}

/** The repository, as its own node: `codeRepository` is not a Dataset property. */
export function softwareSourceCodeNode(): JsonLdNode {
	return {
		"@type": "SoftwareSourceCode",
		"@id": `${SITE_ORIGIN}/#code`,
		name: SITE_NAME,
		description: "Benchmark code, prompts, scorer, and model registries.",
		url: REPO,
		codeRepository: REPO,
		license: "https://www.apache.org/licenses/LICENSE-2.0",
		author: { "@id": authorId },
	};
}

export function pageGraph(input: {
	site: URL;
	canonical: string;
	title: string;
	description: string;
	image: string;
	crumbs: readonly Crumb[];
	extra?: readonly JsonLdNode[] | undefined;
}): JsonLdNode {
	const breadcrumb = breadcrumbNode(input.canonical, input.crumbs, input.site);
	const graph: JsonLdNode[] = [
		organizationNode(input.site),
		websiteNode(input.site),
		personNode(),
		webPageNode({
			canonical: input.canonical,
			title: input.title,
			description: input.description,
			image: input.image,
			breadcrumbId: breadcrumb ? `${input.canonical}#breadcrumb` : undefined,
		}),
	];
	if (breadcrumb) graph.push(breadcrumb);
	if (input.extra) graph.push(...input.extra);
	return {
		"@context": "https://schema.org",
		"@graph": graph,
	};
}

/** Keep a `<` in a string from being read as markup inside the script tag. */
export function jsonLdScript(value: JsonLdNode): string {
	return JSON.stringify(value).replaceAll("<", "\\u003c");
}
