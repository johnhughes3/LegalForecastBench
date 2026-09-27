import type { APIRoute, GetStaticPaths } from "astro";

const sources = import.meta.glob("../../../../data/significance/summary/*", {
	query: "?raw",
	import: "default",
	eager: true,
});
export const getStaticPaths = (() =>
	Object.entries(sources).map(([path, data]) => ({
		params: { file: path.split("/").at(-1) },
		props: { data },
	}))) satisfies GetStaticPaths;
export const GET: APIRoute = ({ props, params }) => {
	if (typeof props.data !== "string")
		throw new Error("Missing summary significance download");
	return new Response(props.data, {
		headers: {
			"Content-Type": params.file?.endsWith(".jsonl")
				? "application/x-ndjson"
				: "application/json",
		},
	});
};
