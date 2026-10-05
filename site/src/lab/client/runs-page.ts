/**
 * Full runs page behavior: a task-directory search, and the all-criteria
 * scanner. The scanner's compact index (one array per criterion) is fetched
 * once, when the section nears the viewport or a filter is set, and rows are
 * drawn in batches so 2,858 criteria never sit in the DOM at once.
 */
import { matchesQuery } from "../filter-state.js";
import { maskFor, matchesMask } from "../flags.js";
import {
	criterionId,
	type IndexRow,
	type LabIndex,
	reviewVerdictOf,
} from "../index-format.js";
import {
	aiStatusHtml,
	escapeHtml,
	gradePairHtml,
	reviewBadgeHtml,
} from "../markup.js";
import { labCriterionPath, labReviewPath } from "../paths.js";
import type { AiStatus, Verdict } from "../types.js";
import { bindFilterBar } from "./filter-controls.js";

const BATCH = 100;

// Task directory: a plain text filter over the 52 static rows.
const taskSearch =
	document.querySelector<HTMLInputElement>("[data-task-search]");
const taskRows = [...document.querySelectorAll<HTMLElement>("[data-task-row]")];
const taskCount = document.querySelector<HTMLElement>("[data-task-count]");
taskSearch?.addEventListener("input", () => {
	let shown = 0;
	for (const row of taskRows) {
		const visible = matchesQuery(row.textContent ?? "", taskSearch.value);
		row.hidden = !visible;
		if (visible) shown += 1;
	}
	if (taskCount)
		taskCount.textContent =
			shown === taskRows.length
				? `Showing all ${taskRows.length} tasks`
				: `Showing ${shown} of ${taskRows.length} tasks`;
});

const section = document.querySelector<HTMLElement>("[data-scanner]");
const form = section?.querySelector<HTMLFormElement>("[data-lab-filters]");
const results = section?.querySelector<HTMLOListElement>("[data-results]");
const more = section?.querySelector<HTMLButtonElement>("[data-more]");
const url = section?.dataset.indexUrl;

const STATUS: readonly (AiStatus | null)[] = [null, "arguable", "problematic"];

function rowHtml(index: LabIndex, row: IndexRow): string {
	const [taskIndex, number, title, , sol, opus, fails, review] = row;
	const task = index.tasks[taskIndex];
	if (!task) return "";
	const id = criterionId(number);
	// Bit i of `fails` is GRADE_SLOTS[i]: Luna/Sonnet, Luna/GPT, Opus/Sonnet, Opus/GPT.
	const verdict = (bit: number): Verdict =>
		(fails >> bit) & 1 ? "fail" : "pass";
	const reviewed = reviewVerdictOf(row);
	return `<li class="flex flex-wrap items-start gap-x-3 gap-y-1.5 rounded-lg border border-rule bg-surface px-3 py-2.5"><span class="w-14 shrink-0 pt-0.5 font-mono text-xs text-ink-3">${id}</span><span class="min-w-[14rem] flex-1"><a class="text-sm font-medium leading-snug text-ink hover:text-accent" href="${labCriterionPath(task.slug, id)}">${escapeHtml(title)}</a><span class="block text-xs text-ink-3">${escapeHtml(task.title)}</span><span class="mt-1 flex flex-wrap items-center gap-1.5">${reviewed ? `<a href="${labReviewPath(review)}" aria-label="Hand-audited item ${review}: reviewer verdict ${reviewed}">${reviewBadgeHtml(reviewed, review)}</a>` : ""}${aiStatusHtml("Sol", STATUS[sol] ?? null)}${aiStatusHtml("Opus", STATUS[opus] ?? null)}</span></span><span class="flex shrink-0 flex-col gap-1">${gradePairHtml("luna", verdict(0), verdict(1))}${gradePairHtml("opus", verdict(2), verdict(3))}</span></li>`;
}

if (section && form && results && more && url) {
	let index: Promise<LabIndex> | undefined;
	const load = (): Promise<LabIndex> => {
		index ??= fetch(url).then((response) => {
			if (!response.ok) throw new Error(`HTTP ${response.status}`);
			return response.json() as Promise<LabIndex>;
		});
		return index;
	};

	let matches: IndexRow[] = [];
	let drawn = 0;
	let data: LabIndex | undefined;

	const status = (text: string) => controls.setCount(text);
	const draw = (focusFirst = false): void => {
		if (!data) return;
		const firstNew = results.children.length;
		const next = matches.slice(drawn, drawn + BATCH);
		results.insertAdjacentHTML(
			"beforeend",
			next.map((row) => (data ? rowHtml(data, row) : "")).join(""),
		);
		drawn += next.length;
		more.hidden = drawn >= matches.length;
		// Keep keyboard focus in the list: the button may hide when the list ends.
		if (focusFirst) results.children[firstNew]?.querySelector("a")?.focus();
		more.textContent = `Show ${Math.min(BATCH, matches.length - drawn)} more (${drawn} of ${matches.length} shown)`;
	};

	const apply = async (): Promise<void> => {
		const state = controls.state();
		try {
			data ??= await load();
		} catch {
			index = undefined;
			status("The criterion index could not be loaded. Reload to retry.");
			return;
		}
		const mask = maskFor(state.filters);
		const taskNumber =
			state.task === ""
				? -1
				: data.tasks.findIndex((t) => t.slug === state.task);
		matches = data.rows.filter((row) => {
			if (taskNumber !== -1 && row[0] !== taskNumber) return false;
			if (!matchesMask(row[3], mask)) return false;
			if (state.query === "") return true;
			const task = data?.tasks[row[0]];
			return matchesQuery(
				`${criterionId(row[1])} ${row[2]} ${task?.title ?? ""}`,
				state.query,
			);
		});
		results.replaceChildren();
		drawn = 0;
		draw();
		status(
			`${matches.length.toLocaleString("en-US")} of ${data.rows.length.toLocaleString("en-US")} criteria match`,
		);
	};

	const controls = bindFilterBar(form, () => {
		void apply();
	});
	more.addEventListener("click", () => draw(true));

	// Fetch the index when the section approaches the viewport, or at once when
	// the URL already carries a filter.
	const start = (): void => {
		status("Loading the criterion index…");
		void apply();
	};
	const filtered = controls.state();
	if (
		filtered.filters.length > 0 ||
		filtered.query !== "" ||
		filtered.task !== "" ||
		!("IntersectionObserver" in window)
	) {
		start();
	} else {
		const observer = new IntersectionObserver(
			(entries) => {
				if (entries.some((entry) => entry.isIntersecting)) {
					observer.disconnect();
					start();
				}
			},
			{ rootMargin: "600px" },
		);
		observer.observe(section);
		// A first interaction also starts the load.
		form.addEventListener(
			"pointerdown",
			() => {
				observer.disconnect();
				start();
			},
			{ once: true },
		);
	}
}
