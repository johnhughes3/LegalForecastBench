import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, resolve, sep } from "node:path";
import test from "node:test";
import { chromium } from "playwright";
import { formatPercent } from "../src/data/metrics";
import { snapshot } from "../src/data/results";

test("navigation fits desktop, tablet, and narrow mobile widths", async () => {
	const root = resolve("dist");
	const types: Record<string, string> = {
		".html": "text/html",
		".css": "text/css",
		".js": "text/javascript",
		".woff2": "font/woff2",
	};
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
			const bytes = await readFile(file);
			response
				.writeHead(200, {
					"Content-Type": types[extname(file)] ?? "application/octet-stream",
				})
				.end(bytes);
		} catch {
			response.writeHead(404).end();
		}
	});
	await new Promise<void>((ready) => server.listen(0, "127.0.0.1", ready));
	const address = server.address();
	assert.ok(address && typeof address !== "string");
	try {
		const browser = await chromium.launch();
		try {
			for (const width of [1280, 768, 1024, 1023, 640, 390, 320]) {
				for (const colorScheme of ["light", "dark"] as const) {
					const page = await browser.newPage({
						viewport: { width, height: 900 },
						colorScheme,
					});
					await page.goto(`http://127.0.0.1:${address.port}/data/`);
					await page.evaluate(() => document.fonts.ready);
					const context = `${width}px ${colorScheme}`;
					assert.ok(
						await page.evaluate(
							() => document.documentElement.scrollWidth <= innerWidth,
						),
						context,
					);
					const nav = page.getByRole("navigation", {
						name: width >= 1024 ? "Primary" : "Primary (mobile)",
						exact: true,
					});
					assert.ok(await nav.isVisible(), context);
					// Below 640px the paper action leads the mobile nav row instead of
					// crowding the header.
					const narrow = width < 640;
					assert.equal(
						await nav.getByRole("link").count(),
						narrow ? 3 : 2,
						context,
					);
					assert.equal(
						await nav
							.getByRole("link", { name: "Data & Code", exact: true })
							.getAttribute("aria-current"),
						"page",
					);
					const brand = await page
						.getByRole("banner")
						.getByRole("link", { name: "LegalForecastBench", exact: true })
						.boundingBox();
					const toggle = await page
						.getByRole("button", { name: "Toggle dark mode" })
						.boundingBox();
					assert.ok(brand && toggle);
					assert.ok(
						brand.x + brand.width <= toggle.x &&
							toggle.x + toggle.width <= width,
						context,
					);
					// The paper action stays in the header row at every width.
					const paper = await page
						.locator('body > header a[href="/paper/"]:visible')
						.boundingBox();
					assert.ok(
						paper &&
							(narrow
								? paper.x >= 0 && paper.x + paper.width <= width
								: brand.x + brand.width <= paper.x &&
									paper.x + paper.width <= toggle.x),
						`${context}: paper action is visible in the header`,
					);
					if (width >= 1024) {
						const box = await nav.boundingBox();
						assert.ok(
							box &&
								brand.x + brand.width <= box.x &&
								box.x + box.width <= toggle.x,
							context,
						);
					}
					// Tab to the last link: the mobile scroller must reveal keyboard focus.
					await nav.getByRole("link", { name: "Results", exact: true }).focus();
					await page.keyboard.press("Tab");
					const lastLink = nav.getByRole("link", {
						name: "Data & Code",
						exact: true,
					});
					assert.ok(
						await lastLink.evaluate(
							(element) => element === document.activeElement,
						),
						context,
					);
					const lastBox = await lastLink.boundingBox();
					assert.ok(
						lastBox && lastBox.x >= 0 && lastBox.x + lastBox.width <= width,
						context,
					);
					await page.getByRole("button", { name: "Toggle dark mode" }).click();
					assert.equal(
						await page.locator("html").getAttribute("data-theme"),
						colorScheme === "light" ? "dark" : "light",
					);
					await page.goto(`http://127.0.0.1:${address.port}/`);
					const dismissalRate = formatPercent(
						snapshot.cohort.dismissed_unit_count / snapshot.cohort.unit_count,
					);
					const dismissalStat = page
						.getByText("Dismissal base rate", { exact: true })
						.locator("..");
					assert.equal(
						await dismissalStat.locator("p").first().textContent(),
						dismissalRate,
						`${context}: home cohort rate matches the shared formatter`,
					);
					await page.close();
				}
			}
		} finally {
			await browser.close();
		}
	} finally {
		await new Promise<void>((done, reject) =>
			server.close((error) => (error ? reject(error) : done())),
		);
	}
});
