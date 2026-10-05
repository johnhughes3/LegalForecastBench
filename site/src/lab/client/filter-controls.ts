/**
 * Wire the shared FilterBar form to a callback and the page URL.
 * The caller owns what "applying" means (hide rows, re-render a list).
 */
import {
	EMPTY_FILTER_STATE,
	type FilterState,
	parseFilterState,
	serializeFilterState,
} from "../filter-state.js";
import { type FilterKey, isFilterKey } from "../flags.js";

export type FilterControls = {
	state: () => FilterState;
	/** Replace the whole state, e.g. to clear filters before jumping to a row. */
	set: (state: FilterState) => void;
	setCount: (text: string) => void;
	/** Apply the current state once, e.g. when the page loads with a filtered URL. */
	refresh: () => void;
};

export function bindFilterBar(
	form: HTMLFormElement,
	onChange: (state: FilterState) => void,
): FilterControls {
	const chips = [...form.querySelectorAll<HTMLButtonElement>("[data-filter]")];
	const input = form.querySelector<HTMLInputElement>("[data-query]");
	const select = form.querySelector<HTMLSelectElement>("[data-task]");
	const clear = form.querySelector<HTMLButtonElement>("[data-clear]");
	const count = form.querySelector<HTMLElement>("[data-count]");
	let current: FilterState = parseFilterState(location.search);

	const render = (): void => {
		for (const chip of chips) {
			const key = chip.dataset.filter ?? "";
			chip.setAttribute(
				"aria-pressed",
				String(isFilterKey(key) && current.filters.includes(key)),
			);
		}
		if (input && input.value !== current.query) input.value = current.query;
		if (select && select.value !== current.task) select.value = current.task;
		const active =
			current.filters.length > 0 || current.query !== "" || current.task !== "";
		if (clear) clear.hidden = !active;
	};
	const commit = (next: FilterState): void => {
		current = next;
		render();
		const query = serializeFilterState(current);
		history.replaceState(
			null,
			"",
			`${location.pathname}${query ? `?${query}` : ""}${location.hash}`,
		);
		onChange(current);
	};

	form.addEventListener("submit", (event) => event.preventDefault());
	for (const chip of chips) {
		chip.addEventListener("click", () => {
			const key = chip.dataset.filter;
			if (!key || !isFilterKey(key)) return;
			const filters: FilterKey[] = current.filters.includes(key)
				? current.filters.filter((existing) => existing !== key)
				: [...current.filters, key];
			commit({ ...current, filters });
		});
	}
	let timer: ReturnType<typeof setTimeout> | undefined;
	input?.addEventListener("input", () => {
		clearTimeout(timer);
		timer = setTimeout(() => commit({ ...current, query: input.value }), 150);
	});
	select?.addEventListener("change", () =>
		commit({ ...current, task: select.value }),
	);
	clear?.addEventListener("click", () => commit(EMPTY_FILTER_STATE));

	render();
	return {
		refresh: () => onChange(current),
		state: () => current,
		set: commit,
		setCount: (text) => {
			if (count) count.textContent = text;
		},
	};
}
