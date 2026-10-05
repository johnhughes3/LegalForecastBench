/**
 * Filter state for the explorer's criterion lists, kept in the URL so a
 * filtered view can be shared or reloaded. Pure functions; the DOM scripts
 * call them and the tests exercise them directly.
 */
import { type FilterKey, isFilterKey } from "./flags.js";

export type FilterState = {
	filters: readonly FilterKey[];
	query: string;
	/** Task slug, or "" for all tasks (the all-criteria scanner only). */
	task: string;
};

export const EMPTY_FILTER_STATE: FilterState = {
	filters: [],
	query: "",
	task: "",
};

export function parseFilterState(search: string): FilterState {
	const params = new URLSearchParams(search);
	const filters = (params.get("f") ?? "")
		.split(",")
		.filter((value): value is FilterKey => isFilterKey(value));
	return {
		filters: [...new Set(filters)],
		query: (params.get("q") ?? "").slice(0, 200),
		task: params.get("task") ?? "",
	};
}

/** Query string for a state, without the leading "?"; empty when nothing is set. */
export function serializeFilterState(state: FilterState): string {
	const params = new URLSearchParams();
	if (state.filters.length > 0) params.set("f", state.filters.join(","));
	if (state.query.trim() !== "") params.set("q", state.query.trim());
	if (state.task !== "") params.set("task", state.task);
	return params.toString();
}

/** Every whitespace-separated term must appear, case-insensitively. */
export function matchesQuery(haystack: string, query: string): boolean {
	const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
	if (terms.length === 0) return true;
	const text = haystack.toLowerCase();
	return terms.every((term) => text.includes(term));
}
