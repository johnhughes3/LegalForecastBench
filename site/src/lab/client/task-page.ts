/**
 * Task page behavior: filter the criterion list, open or close every row, and
 * fetch the judges' reasoning (one static file for the whole task) the first
 * time a row is opened.
 */
import { matchesQuery } from "../filter-state.js";
import { maskFor, matchesMask } from "../flags.js";
import type { TaskDetail } from "../index-format.js";
import { criterionBodyHtml } from "../markup.js";
import { bindFilterBar } from "./filter-controls.js";

const list = document.querySelector<HTMLElement>("[data-criteria]");
const form = document.querySelector<HTMLFormElement>("[data-lab-filters]");

if (list && form) {
	const rows = [...list.querySelectorAll<HTMLElement>("[data-crit]")];
	const details = rows
		.map((row) => row.querySelector<HTMLDetailsElement>("details"))
		.filter((element): element is HTMLDetailsElement => element !== null);
	const texts = new WeakMap<HTMLElement, string>();
	const textOf = (row: HTMLElement): string => {
		let text = texts.get(row);
		if (text === undefined) {
			text = row.textContent ?? "";
			texts.set(row, text);
		}
		return text;
	};

	const controls = bindFilterBar(form, (state) => {
		const mask = maskFor(state.filters);
		let shown = 0;
		for (const row of rows) {
			const flags = Number(row.dataset.flags ?? 0);
			const visible =
				matchesMask(flags, mask) &&
				(state.query === "" || matchesQuery(textOf(row), state.query));
			row.hidden = !visible;
			if (visible) shown += 1;
		}
		controls.setCount(
			shown === rows.length
				? `Showing all ${rows.length} criteria`
				: `Showing ${shown} of ${rows.length} criteria`,
		);
	});

	controls.refresh();

	for (const button of document.querySelectorAll<HTMLButtonElement>(
		"[data-expand]",
	)) {
		button.addEventListener("click", () => {
			const open = button.dataset.expand === "all";
			for (const element of details) {
				if (!element.closest("[data-crit]")?.hasAttribute("hidden"))
					element.open = open;
			}
		});
	}

	// One fetch per page view, shared by every row, started on the first hover
	// or keyboard focus so it is usually done by the time a row opens.
	let detail: Promise<TaskDetail> | undefined;
	const loadDetail = (): Promise<TaskDetail> => {
		const url = list.dataset.detailUrl;
		if (!url) return Promise.reject(new Error("No detail URL"));
		detail ??= fetch(url).then((response) => {
			if (!response.ok) throw new Error(`HTTP ${response.status}`);
			return response.json() as Promise<TaskDetail>;
		});
		return detail;
	};
	const fill = async (element: HTMLDetailsElement): Promise<void> => {
		const body = element.querySelector<HTMLElement>("[data-body]");
		if (!body || element.dataset.filled) return;
		element.dataset.filled = "1";
		try {
			const payload = await loadDetail();
			const own = payload.criteria[Number(element.dataset.index)];
			if (!own) throw new Error("Criterion missing from detail");
			body.innerHTML = criterionBodyHtml(payload.task, own);
		} catch {
			element.dataset.filled = "";
			detail = undefined;
			body.textContent =
				"The rubric text and grades could not be loaded. Close and reopen this row to retry.";
		}
	};
	for (const element of details) {
		element.addEventListener("toggle", () => {
			if (element.open) void fill(element);
		});
	}
	list.addEventListener(
		"pointerover",
		() => void loadDetail().catch(() => {}),
		{
			once: true,
		},
	);
	list.addEventListener("focusin", () => void loadDetail().catch(() => {}), {
		once: true,
	});

	// A link to #c-012 opens that row, clearing any filter that hides it.
	const openHash = (): void => {
		const id = decodeURIComponent(location.hash.slice(1));
		const row = id ? rows.find((candidate) => candidate.id === id) : undefined;
		if (!row) return;
		if (row.hidden) controls.set({ filters: [], query: "", task: "" });
		const element = row.querySelector("details");
		if (element) element.open = true;
		row.scrollIntoView({ block: "start" });
	};
	addEventListener("hashchange", openHash);
	openHash();
}
