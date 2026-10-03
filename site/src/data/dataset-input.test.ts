import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
	existsSync,
	mkdirSync,
	mkdtempSync,
	readFileSync,
	rmSync,
	writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import {
	copyRefreshedDownloads,
	datasetJson,
	selectDatasetDirectory,
} from "./dataset-input.js";
import { repositoryRoot } from "./manuscript.js";

test("default dataset input preserves checked-in values", () => {
	const fallback = { cases: 91 };
	assert.equal(datasetJson("current.json", fallback), fallback);
});

test("refresh replaces every download while preserving newly rendered pages", () => {
	const root = mkdtempSync(join(tmpdir(), "lfb-downloads-"));
	try {
		const source = join(root, "source");
		const built = join(root, "built");
		mkdirSync(join(source, "summary-comparison"), { recursive: true });
		mkdirSync(join(built, "exports"), { recursive: true });
		for (const name of [
			"current.json",
			"sources.json",
			"historical-aggregates.json",
		])
			writeFileSync(join(source, name), "{}\n");
		writeFileSync(
			join(source, "summary-comparison", "forecasts.json"),
			'"retained-case"',
		);
		writeFileSync(join(source, "index.html"), "stale original cohort");
		writeFileSync(join(built, "index.html"), "new retained cohort");
		writeFileSync(join(built, "exports", "withdrawn.json"), '"withdrawn-case"');
		writeFileSync(join(built, "stale.jsonl"), '"withdrawn-case"');
		copyRefreshedDownloads(source, built);
		assert.equal(existsSync(join(built, "exports", "withdrawn.json")), false);
		assert.equal(existsSync(join(built, "stale.jsonl")), false);
		assert.equal(
			readFileSync(join(built, "index.html"), "utf8"),
			"new retained cohort",
		);
		assert.equal(
			readFileSync(join(built, "summary-comparison", "forecasts.json"), "utf8"),
			'"retained-case"',
		);
		assert.throws(() => copyRefreshedDownloads(built, built), /separate/);
		rmSync(join(source, "historical-aggregates.json"));
		assert.throws(() => copyRefreshedDownloads(source, built), /Incomplete/);
		assert.equal(
			readFileSync(join(built, "index.html"), "utf8"),
			"new retained cohort",
		);
	} finally {
		rmSync(root, { recursive: true });
	}
});

test("persistent generated input is selected without deployment environment changes", () => {
	const root = mkdtempSync(join(tmpdir(), "lfb-persistent-"));
	try {
		assert.equal(selectDatasetDirectory(undefined, root), undefined);
		const selected = join(root, "site/refreshed-data");
		mkdirSync(selected, { recursive: true });
		writeFileSync(join(selected, "current.json"), "{}");
		assert.equal(selectDatasetDirectory(undefined, root), selected);
		assert.equal(selectDatasetDirectory("", root), undefined);
		const explicit = join(root, "explicit");
		assert.throws(
			() => selectDatasetDirectory(explicit, root),
			/missing current.json/,
		);
		mkdirSync(explicit);
		writeFileSync(join(explicit, "current.json"), "{}");
		assert.equal(selectDatasetDirectory(explicit, root), explicit);
	} finally {
		rmSync(root, { recursive: true });
	}
});

test("publication producer rejects shell syntax before building", () => {
	const result = spawnSync(
		"bash",
		[join(repositoryRoot(), "site/scripts/build-selected-data.sh")],
		{
			env: {
				...process.env,
				WITHDRAWN_CASE_IDS: "synthetic-case-b;touch forbidden",
			},
			encoding: "utf8",
		},
	);
	assert.equal(result.status, 1);
	assert.match(result.stderr, /Withdrawal case IDs/);
	assert.equal(result.stdout, "");
});
