import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import empirical from "../../../docs/papers/legalforecastbench/data/empirical.json" with {
	type: "json",
};
import { receiptCosts } from "./receipt-costs.js";
import { primarySnapshot } from "./results.js";

test("every ranked configuration has the same cost and basis in paper data and site", () => {
	assert.deepEqual(
		primarySnapshot.models.map((model) => model.slug).sort(),
		empirical.models.map((model) => model.slug).sort(),
	);
	for (const model of primarySnapshot.models) {
		const paper = empirical.models.find((row) => row.slug === model.slug);
		assert.ok(paper, model.slug);
		assert.equal(paper.cost.usd, model.cost.usd, `${model.slug}: USD`);
		const receipt = receiptCosts.find((row) => row.slug === model.slug);
		if (receipt) {
			assert.equal(
				model.cost.basis,
				receipt.standard_rate_estimate_usd === null
					? "unavailable"
					: "estimated",
				`${model.slug}: site basis`,
			);
		}
		// Paper data names the reconstruction method; the site labels those
		// same amounts as estimates and exposes the method in its cost note.
		assert.equal(
			paper.cost.basis,
			receipt?.standard_rate_method ?? model.cost.basis,
			`${model.slug}: basis`,
		);
	}
});

test("the printed main table agrees with every ranked paper cost", () => {
	const manuscript = readFileSync(
		new URL(
			"../../../docs/papers/legalforecastbench/LegalForecastBench-paper.tex",
			import.meta.url,
		),
		"utf8",
	);
	const tables = manuscript.match(/\\begin\{table\}[\s\S]*?\\end\{table\}/g);
	const table = tables?.find((block) => block.includes("\\label{tab:main}"));
	assert.ok(table, "main results table must exist");
	// The ranked panel lies between the header and reference-panel rules.
	const panel = table.split("\\midrule")[1];
	assert.ok(panel);
	const rows = panel
		.split("\n")
		.filter((line) => line.includes("&"))
		.map((line) => {
			const cells = line.split("&").map((cell) => cell.trim());
			assert.equal(cells.length, 6, `unrecognized main-table row: ${line}`);
			return [cells[0], cells[5]?.replace(/\\\\.*$/, "").trim()] as const;
		});
	assert.equal(rows.length, empirical.models.length);
	assert.equal(new Set(rows.map(([name]) => name)).size, rows.length);
	for (const model of empirical.models) {
		const printed = rows.find(([name]) => name === model.display_name);
		assert.ok(printed, `${model.display_name}: missing printed row`);
		assert.equal(
			printed[1],
			model.cost.usd === null ? "---" : model.cost.usd.toFixed(2),
			`${model.slug}: printed USD`,
		);
	}
});

test("Cycle 1 archived-receipt reference totals cannot revert together", () => {
	// Independently recomputed from the frozen registries and all 91 receipts
	// per run in #1374. Pin run identities, not live prices or provider charges.
	// These references catch agreement on the same obsolete calculation across
	// paper and site; new runs still undergo the general checks above.
	const references = [
		["35776235829", "35885171489", 11.0952015],
		["35933696453", "35940612024", 0.633156565],
		["35953489581", "35954306953", 20.5866604],
		["35799524684", "35885175070", 32.999826],
		["35954543028", "36073985227", 38.34943],
		["36075557088", "36169561374", 27.734889],
		["36673524599", "36741462923", 10.8519246],
		["36673527185", "36741468019", 6.992409],
		["38300603621", "38303872484", 39.3793984],
		["39155697923", "39189136234", 25.0204571],
		["39193012515", "39195758917", 16.6489902],
		["38897535768", "38992564711", 1.34912112],
	] as const;
	for (const [forecast, scoring, expected] of references) {
		const row = receiptCosts.find(
			(cost) =>
				cost.forecast_run_id === forecast && cost.score_run_id === scoring,
		);
		assert.ok(
			row,
			`missing archived-receipt reference: ${forecast}/${scoring}`,
		);
		assert.ok(
			row.standard_rate_estimate_usd !== null &&
				Math.abs(row.standard_rate_estimate_usd - expected) < 1e-10,
			`${row.slug}: expected archived standard-rate USD ${expected}, got ${row.standard_rate_estimate_usd}`,
		);
	}
});
