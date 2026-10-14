import assert from "node:assert/strict";
import test from "node:test";
import { AUTHOR, REPO } from "../data/author";
import { engagementEvent } from "../scripts/engagement";

const origin = "https://benchmark.example";

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
