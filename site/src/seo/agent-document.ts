export interface AgentDocument {
	/** Path under `/agent/`, without a leading slash. */
	slug: string;
	/** Canonical HTML path, with a trailing slash. */
	path: string;
	title: string;
	description: string;
	markdown: string;
}
