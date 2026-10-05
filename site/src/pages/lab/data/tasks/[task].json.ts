import type { APIRoute, GetStaticPaths } from "astro";
import { buildDetail } from "../../../../lab/index-format";
import { loadLab } from "../../../../lab/load";

export const getStaticPaths = (() =>
	loadLab().tasks.map((task) => ({
		params: { task: task.slug },
		props: { payload: buildDetail(task) },
	}))) satisfies GetStaticPaths;

/** One task's judge reasoning, fetched when a reader opens a criterion. */
export const GET: APIRoute = ({ props }) =>
	new Response(JSON.stringify(props.payload), {
		headers: { "Content-Type": "application/json" },
	});
