import type { Faq } from "./faqs.js";
import {
	AUTHOR,
	authorId,
	LOGO_PATH,
	organizationId,
	REPO,
	SITE_NAME,
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
		sameAs: [REPO, AUTHOR.github, AUTHOR.linkedin, AUTHOR.x],
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
		url: AUTHOR.site,
		sameAs: [AUTHOR.github, AUTHOR.linkedin, AUTHOR.x],
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
	});
}

export function datasetNode(input: {
	name: string;
	description: string;
	url: string;
	temporalCoverage: string;
	contentUrl: string;
}): JsonLdNode {
	return {
		"@type": "Dataset",
		"@id": `${input.url}#dataset`,
		name: input.name,
		description: input.description,
		url: input.url,
		creator: { "@id": authorId },
		publisher: { "@id": organizationId },
		temporalCoverage: input.temporalCoverage,
		isAccessibleForFree: true,
		license: "https://creativecommons.org/licenses/by/4.0/",
		distribution: [
			{
				"@type": "DataDownload",
				encodingFormat: "application/json",
				contentUrl: input.contentUrl,
			},
		],
		codeRepository: REPO,
	};
}

export function faqPageNode(
	canonical: string,
	faqs: readonly Faq[],
): JsonLdNode {
	return {
		"@type": "FAQPage",
		"@id": `${canonical}#faq`,
		url: canonical,
		mainEntity: faqs.map((faq) => ({
			"@type": "Question",
			name: faq.question,
			acceptedAnswer: {
				"@type": "Answer",
				text: faq.answer,
			},
		})),
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
