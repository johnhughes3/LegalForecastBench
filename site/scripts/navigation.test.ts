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
					await page.goto(`http://127.0.0.1:${address.port}/approach/`);
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
					assert.equal(await nav.getByRole("link").count(), 6);
					assert.equal(
						await nav
							.getByRole("link", { name: "Approach", exact: true })
							.getAttribute("aria-current"),
						"page",
					);
					const brand = await page
						.locator("body > header > div > a")
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
					for (let index = 0; index < 5; index++)
						await page.keyboard.press("Tab");
					const lastLink = nav.getByRole("link", { name: "Data", exact: true });
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
					await page.goto(`http://127.0.0.1:${address.port}/methods/`);
					const dismissalRate = formatPercent(
						snapshot.cohort.dismissed_unit_count / snapshot.cohort.unit_count,
					);
					const dismissalStat = page
						.getByText("Units dismissed", { exact: true })
						.locator("..");
					assert.equal(
						await dismissalStat.locator("p").first().textContent(),
						dismissalRate,
						`${context}: methods cohort rate matches the shared formatter`,
					);
					assert.equal(
						await page
							.getByText(
								`Always forecast the cohort's dismissal rate (${dismissalRate})`,
								{ exact: true },
							)
							.count(),
						1,
						`${context}: methods baseline uses the same rate`,
					);
					assert.equal(
						await page
							.getByRole("heading", {
								name: "Construct And Intended Use",
								level: 3,
								exact: true,
							})
							.count(),
						1,
						`${context}: technical sections nest beneath the appendix`,
					);
					assert.equal(
						await page
							.getByRole("heading", {
								name: "Model eligibility and contamination",
								level: 4,
								exact: true,
							})
							.count(),
						1,
						`${context}: technical subsections retain their hierarchy`,
					);
					if (width === 390) {
						await page.goto(
							`http://127.0.0.1:${address.port}/findings/first-release/`,
						);
						const region = page.getByRole("region", {
							name: "High-confidence predictions",
						});
						assert.equal(await region.getAttribute("tabindex"), "0");
						await region.focus();
						assert.ok(
							await region.evaluate(
								(element) => element === document.activeElement,
							),
						);
						await page.keyboard.press("ArrowRight");
						await page.waitForFunction(
							() =>
								(document.querySelector(
									'[aria-label="High-confidence predictions"]',
								)?.scrollLeft ?? 0) > 0,
						);
					}
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
