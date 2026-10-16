import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";

const source = readFileSync(
	new URL("../components/AnalyticsPrivacy.astro", import.meta.url),
	"utf8",
);
const script =
	source.match(/<script is:inline>([\s\S]*?)<\/script>/)?.[1] ?? "";
assert.notEqual(script, "");

function policy(
	preferences: {
		dnt?: string;
		gpc?: boolean;
		optOut?: string;
		blocked?: boolean;
	} = {},
) {
	const window = {} as {
		webAnalyticsBeforeSend: (event: {
			type: string;
			url: string;
		}) => { type: string; url: string } | null;
	};
	runInNewContext(script, {
		window,
		URL,
		navigator: {
			doNotTrack: preferences.dnt,
			globalPrivacyControl: preferences.gpc,
		},
		localStorage: {
			getItem: () => {
				if (preferences.blocked) throw new Error("blocked");
				return preferences.optOut;
			},
		},
	});
	return window.webAnalyticsBeforeSend;
}

test("page views and custom events lose query strings and fragments", () => {
	for (const type of ["pageview", "event"]) {
		assert.equal(
			policy()({ type, url: "https://example.org/paper/?email=private#secret" })
				?.url,
			"https://example.org/paper/",
		);
	}
});

test("privacy signals, opt-out and inaccessible preferences suppress all event types", () => {
	for (const preferences of [
		{ dnt: "1" },
		{ gpc: true },
		{ optOut: "1" },
		{ blocked: true },
	]) {
		for (const type of ["pageview", "event"])
			assert.equal(
				policy(preferences)({ type, url: "https://example.org/" }),
				null,
			);
	}
	assert.equal(policy()({ type: "pageview", url: "invalid" }), null);
});
