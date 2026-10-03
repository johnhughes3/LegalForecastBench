import type { APIRoute, GetStaticPaths } from "astro";
import { datasetDownloads } from "../../../data/dataset-input.js";

const sources = import.meta.glob("../../../data/significance/*", {
	query: "?raw",
	import: "default",
	eager: true,
});
export const getStaticPaths = (() =>
	Object.entries(datasetDownloads("significance", sources)).map(
		([path, data]) => ({
			params: { file: path.split("/").at(-1) },
			props: { data },
		}),
	)) satisfies GetStaticPaths;
export const GET: APIRoute = ({ props, params }) => {
	if (typeof props.data !== "string")
		throw new Error("Missing significance download");
	return new Response(props.data, {
		headers: {
			"Content-Type": params.file?.endsWith(".jsonl")
				? "application/x-ndjson"
				: "application/json",
		},
	});
};
