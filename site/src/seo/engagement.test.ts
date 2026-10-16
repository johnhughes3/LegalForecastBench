import assert from "node:assert/strict";
import test from "node:test";
import { AUTHOR, REPO } from "../data/author";
import { engagementDestination, engagementEvent } from "../scripts/engagement";

const origin = "https://benchmark.example";

test("destination metadata contains only fixed site categories", () => {
	for (const [href, expected] of [
		["/paper/?private=1", "legalforecastbench"],
		[AUTHOR.contact, "personal_site"],
		[REPO, "github"],
		["mailto:private@example.org", "email"],
	] as const) {
		assert.equal(
			engagementDestination(new URL(href, origin), origin),
			expected,
		);
	}
});

test("meaningful research destinations produce distinct fixed action names", () => {
	for (const [href, expected] of [
		["/paper/", "paper_click"],
		["/paper/working.pdf?download=1", "paper_click"],
		["/data/", "code_data_click"],
		["/data/results.json", "code_data_click"],
		[REPO, "code_data_click"],
		[`${REPO}/tree/main`, "code_data_click"],
		[AUTHOR.contact, "contact_click"],
		[AUTHOR.research, "research_click"],
		["mailto:reader@example.org?subject=Feedback", "email_click"],
	] as const) {
		assert.equal(engagementEvent(new URL(href, origin), origin), expected);
	}
});

test("unrelated links and lookalike external destinations are ignored", () => {
	for (const href of [
		"/#leaderboard",
		"/models/example/",
		"https://unrelated.example/paper/",
		`${REPO}-other`,
		`${AUTHOR.site}practice/`,
	]) {
		assert.equal(engagementEvent(new URL(href, origin), origin), null);
	}
});
