import assert from "node:assert/strict";
import { test } from "node:test";

import { PAPER_CITATION } from "./paper.js";
import { cycleLabel, cycleOf, describeRelease, RELEASE } from "./release.js";

test("the cycle comes from the corpus release id", () => {
	assert.equal(cycleOf("cycle-1-91-2026-09-08-luna-r5"), 1);
	assert.equal(cycleOf("cycle-12-100-2027-01-01-x"), 12);
	assert.throws(() => cycleOf("beta-2026-09-18"), /does not name a cycle/);
});

test("beta results carry the suffix and official results drop it", () => {
	assert.equal(
		cycleLabel("cycle-1-91-2026-09-08-luna-r5", "beta"),
		"Cycle 1 beta",
	);
	assert.equal(
		cycleLabel("cycle-1-91-2026-09-08-luna-r5", "official"),
		"Cycle 1",
	);
});

test("the label pairs the cycle with the publication date", () => {
	const release = describeRelease(
		"cycle-2-100-2027-03-01-x",
		"official",
		"2027-04-02",
	);
	assert.equal(release.label, "Cycle 2 · April 2, 2027");
	assert.equal(release.cycleName, "Cycle 2");
	assert.equal(release.id, "cycle-2-100-2027-03-01-x");
});

test("the published release is Cycle 1, dated by first publication", () => {
	assert.equal(RELEASE.cycle, 1);
	assert.equal(RELEASE.publishedOn, PAPER_CITATION.date);
	assert.match(RELEASE.label, /^Cycle 1( beta)? · [A-Z][a-z]+ \d{1,2}, \d{4}$/);
});
