import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { compileFromFile } from "json-schema-to-typescript";

const schemaPath = fileURLToPath(
	new URL("../../docs/schemas/site-export-v1.schema.json", import.meta.url),
);
const outputPath = fileURLToPath(
	new URL("../src/generated/site-export.ts", import.meta.url),
);
const generated = await compileFromFile(schemaPath, {
	bannerComment:
		"/* Generated from docs/schemas/site-export-v1.schema.json. Run pnpm --filter @legalforecastbench/site contract:generate to update. */",
	unknownAny: true,
});

if (process.argv.includes("--check")) {
	const existing = await readFile(outputPath, "utf8");
	if (existing !== generated) {
		throw new Error(
			"Site contract types are stale. Run pnpm --filter @legalforecastbench/site contract:generate.",
		);
	}
} else {
	await mkdir(dirname(outputPath), { recursive: true });
	await writeFile(outputPath, generated);
}
