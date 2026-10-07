import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, resolve, sep } from "node:path";
import test from "node:test";
import { chromium } from "playwright";

// Drives the built LAB explorer in a real browser: tab switching, the
// all-criteria scanner and its filters, lazy detail loading on a task page,
// walk-through navigation, and narrow-screen overflow. Requires `pnpm build`.
const root = resolve("dist");
const types: Record<string, string> = {
	".html": "text/html",
	".css": "text/css",
	".js": "text/javascript",
	".json": "application/json",
	".woff2": "font/woff2",
};
const TASK = "assess-reasonableness-of-staffing-levels-on-litigation-invoice";

// The explorer's pages live in src/pages/_lab, which Astro does not route, until
// the LAB audit paper is published; rename the directory back to relaunch.
test("the LAB explorer works end to end in a browser", {
	skip: "the LAB explorer is offline until the audit paper is published",
}, async () => {
	const server = createServer(async (request, response) => {
		const pathname = new URL(request.url ?? "/", "http://localhost").pathname;
		const file = resolve(
			root,
			`.${pathname.endsWith("/") ? `${pathname}index.html` : pathname}`,
		);
		if (!file.startsWith(`${root}${sep}`)) {
			response.writeHead(403).end();
			return;
		}
		try {
			response
				.writeHead(200, {
					"Content-Type": types[extname(file)] ?? "application/octet-stream",
				})
				.end(await readFile(file));
		} catch {
			response.writeHead(404).end();
		}
	});
	await new Promise<void>((ready) => server.listen(0, "127.0.0.1", ready));
	const address = server.address();
	assert.ok(address && typeof address !== "string");
	const base = `http://127.0.0.1:${address.port}`;
	const browser = await chromium.launch();
	try {
		const page = await browser.newPage({
			viewport: { width: 1280, height: 900 },
		});
		const requests: string[] = [];
		page.on("request", (request) =>
			requests.push(new URL(request.url()).pathname),
		);
		const errors: string[] = [];
		page.on("pageerror", (error) => errors.push(error.message));

		// The landing page is the hand-audited view and loads no criterion index.
		await page.goto(`${base}/lab/`);
		const views = page.getByRole("navigation", { name: "LAB explorer views" });
		assert.equal(
			await views
				.getByRole("link", { name: /Hand-audited/ })
				.getAttribute("aria-current"),
			"page",
		);
		assert.equal((await page.getByRole("row").count()) > 25, true);
		assert.equal(
			requests.some((path) => path.endsWith("/lab/data/index.json")),
			false,
		);

		// Switching tabs is a plain navigation to the full-runs view.
		await views.getByRole("link", { name: /Full runs/ }).click();
		await page.waitForURL(`${base}/lab/runs/`);
		// The index is fetched only once the scanner nears the viewport.
		assert.equal(
			requests.some((path) => path.endsWith("/lab/data/index.json")),
			false,
		);
		await page.locator("#criteria").scrollIntoViewIfNeeded();
		await page.waitForFunction(
			() => document.querySelector("[data-results]")?.children.length === 100,
		);
		const status = page.locator("[data-lab-filters] [data-count]");
		await status.getByText("2,858 of 2,858").waitFor();

		// Filters combine with AND and are reflected in the URL.
		await page.getByRole("button", { name: /^Hand-audited/ }).click();
		await status.getByText("25 of 2,858").waitFor();
		await page.getByRole("button", { name: /^Defective per reviewer/ }).click();
		await status.getByText("16 of 2,858").waitFor();
		assert.match(page.url(), /f=reviewed%2ChumanDefective/);
		await page.getByRole("button", { name: "Clear filters" }).click();
		await status.getByText("2,858 of 2,858").waitFor();
		await page.getByRole("button", { name: /^AI-flagged/ }).click();
		await status.getByText("835 of 2,858").waitFor();

		// A shared filtered URL restores its state.
		await page.goto(`${base}/lab/runs/?f=reviewed`);
		await status.getByText("25 of 2,858").waitFor();
		assert.equal(
			await page
				.getByRole("button", { name: /^Hand-audited/ })
				.getAttribute("aria-pressed"),
			"true",
		);

		// Task page: rows load detail only when opened; a deep link opens its row.
		const detailRequests: string[] = [];
		page.on("request", (request) => {
			const path = new URL(request.url()).pathname;
			if (path.includes("/lab/data/tasks/")) detailRequests.push(path);
		});
		await page.goto(`${base}/lab/tasks/${TASK}/`);
		assert.deepEqual(detailRequests, []);
		await page.goto(`${base}/lab/tasks/${TASK}/#c-049`);
		const row = page.locator("#c-049");
		await row.getByText("Reviewer's verdicts and analysis").waitFor();
		await row.getByText("Rubric criterion").waitFor();
		await row.getByText("Fail", { exact: false }).first().waitFor();
		assert.equal(detailRequests.length, 1);
		assert.ok(
			(await row.locator(".lab-grade-card p").first().innerText()).length > 50,
		);

		// Task-page filters hide rows and a deep link to a hidden row clears them.
		await page.getByRole("button", { name: /^Hand-audited/ }).click();
		await page.getByText(/Showing \d+ of \d+ criteria/).waitFor();
		assert.equal(
			(await page.locator("[data-crit]:not([hidden])").count()) > 0,
			true,
		);
		// Search matches ids and titles, not the grade labels printed on every row.
		await page.goto(`${base}/lab/tasks/${TASK}/?q=opus`);
		await page.getByText(/Showing 0 of \d+ criteria/).waitFor();
		// A malformed hash must not break the page.
		await page.goto(`${base}/lab/tasks/${TASK}/#%E0%A4%A`);
		assert.equal(
			(await page.locator("[data-crit]:not([hidden])").count()) > 0,
			true,
		);
		await page.goto(`${base}/lab/tasks/${TASK}/?f=reviewed#c-001`);
		await page.waitForFunction(
			() => !document.getElementById("c-001")?.hasAttribute("hidden"),
		);

		// Walk-through: 25 items, previous and next links at the ends.
		await page.goto(`${base}/lab/review/1/`);
		assert.equal(await page.getByRole("link", { name: /Previous/ }).count(), 0);
		await page
			.getByRole("link", { name: /^Next \(#2\)/ })
			.first()
			.click();
		await page.waitForURL(`${base}/lab/review/2/`);
		await page.goto(`${base}/lab/review/25/`);
		assert.equal(await page.getByRole("link", { name: /^Next/ }).count(), 0);
		assert.equal(
			await page
				.getByRole("navigation", { name: "Hand-audited items" })
				.locator("ol a")
				.count(),
			25,
		);

		// No page scrolls sideways on a phone.
		for (const path of [
			"/lab/",
			"/lab/runs/",
			`/lab/tasks/${TASK}/`,
			"/lab/review/7/",
		]) {
			const phone = await browser.newPage({
				viewport: { width: 390, height: 844 },
			});
			await phone.goto(`${base}${path}`);
			await phone.waitForTimeout(300);
			assert.ok(
				await phone.evaluate(
					() => document.documentElement.scrollWidth <= innerWidth,
				),
				path,
			);
			await phone.close();
		}
		assert.deepEqual(errors, []);
	} finally {
		await browser.close();
		server.close();
	}
});
