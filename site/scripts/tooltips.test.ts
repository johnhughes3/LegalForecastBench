import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, resolve, sep } from "node:path";
import test from "node:test";
import { chromium } from "playwright";

test("tooltips remain described, dismissible, and visible on static and hydrated pages", async () => {
	const root = resolve("dist");
	const server = createServer(async (request, response) => {
		const path = new URL(request.url ?? "/", "http://localhost").pathname;
		const file = resolve(
			root,
			`.${path.endsWith("/") ? `${path}index.html` : path}`,
		);
		if (!file.startsWith(`${root}${sep}`)) {
			response.writeHead(403).end();
			return;
		}
		try {
			const types: Record<string, string> = {
				".html": "text/html",
				".js": "text/javascript",
				".css": "text/css",
				".woff2": "font/woff2",
				".svg": "image/svg+xml",
			};
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
	const browser = await chromium.launch();
	try {
		for (const nativePopover of [false, true])
			for (const width of [390, 1280])
				for (const colorScheme of ["light", "dark"] as const) {
					const page = await browser.newPage({
						viewport: { width, height: 900 },
						colorScheme,
						hasTouch: width === 390,
						reducedMotion: "reduce",
					});
					const errors: string[] = [];
					if (!nativePopover)
						await page.addInitScript(() => {
							Reflect.deleteProperty(HTMLElement.prototype, "showPopover");
							Reflect.deleteProperty(HTMLElement.prototype, "hidePopover");
						});
					page.setDefaultTimeout(5_000);
					page.on("pageerror", (error) => errors.push(error.message));
					page.on("console", (message) => {
						if (message.type() === "error") errors.push(message.text());
					});
					for (const path of ["/", "/models/gpt-6-sol/"]) {
						const response = await page.goto(
							`http://127.0.0.1:${address.port}${path}`,
						);
						assert.ok(response);
						if (!nativePopover)
							await page.locator("[popover]").evaluateAll((elements) => {
								// Emulate the older browser's lack of UA popover hiding, too.
								for (const element of elements)
									element.removeAttribute("popover");
							});
						const renderedIds = [
							...(await response.text()).matchAll(
								/role="tooltip" id="([^"]+)"/g,
							),
						]
							.map((match) => match[1])
							.sort();
						await page.evaluate(() => document.fonts.ready);
						if (path === "/")
							await page
								.getByRole("heading", { name: "Forecast quality by model" })
								.scrollIntoViewIfNeeded();
						const triggers = page.locator("button[aria-describedby]:visible");
						assert.equal(
							await page.locator('[role="tooltip"]:visible').count(),
							0,
							"Tooltips start hidden, including without native Popover support",
						);
						assert.ok((await triggers.count()) > 0);
						assert.deepEqual(
							await page.evaluate(() => {
								const ids = [...document.querySelectorAll("[id]")].map(
									(el) => el.id,
								);
								return ids.filter((id, index) => ids.indexOf(id) !== index);
							}),
							[],
							`${path}: unique IDs`,
						);
						assert.deepEqual(
							await page
								.locator('[role="tooltip"]')
								.evaluateAll((elements) => elements.map((el) => el.id).sort()),
							renderedIds,
							"Descriptions retain server-rendered IDs after hydration",
						);
						for (const trigger of await triggers.all()) {
							const id = await trigger.getAttribute("aria-describedby");
							assert.ok(id);
							const tooltip = page.locator(`[role="tooltip"][id="${id}"]`);
							assert.equal(await tooltip.count(), 1);
							await trigger.focus();
							await tooltip.waitFor({ state: "visible" });
							await page.keyboard.press("Escape");
							assert.equal(
								await tooltip.isVisible(),
								false,
								`${path}: Escape dismisses without moving focus`,
							);
							assert.ok(
								await trigger.evaluate((el) => el === document.activeElement),
							);
							await page.mouse.move(1, 1);
							assert.equal(
								await tooltip.isVisible(),
								false,
								"Pointer movement must not undo Escape",
							);
							await trigger.blur();
							if (width === 390) await trigger.tap();
							else await trigger.hover();
							await tooltip.waitFor({ state: "visible" });
							assert.ok(
								await tooltip.evaluate((el) => {
									const box = el.getBoundingClientRect();
									return (
										box.x >= 0 &&
										box.y >= 0 &&
										box.right <= innerWidth &&
										box.bottom <= innerHeight &&
										el.contains(
											document.elementFromPoint(
												box.x + box.width / 2,
												box.y + box.height / 2,
											),
										)
									);
								}),
								`${path}: tooltip inside viewport and not clipped/covered`,
							);
							// Hover content stays available while the pointer moves into it.
							if (width === 1280) {
								await tooltip.hover();
								assert.ok(await tooltip.isVisible());
							}
							// The viewport gutter is outside the tooltip even when it covers a heading.
							if (width === 390) await page.touchscreen.tap(2, 2);
							else await page.mouse.click(2, 2);
							assert.equal(
								await tooltip.isVisible(),
								false,
								`${path}: outside dismissal`,
							);
						}
						assert.ok(
							await page.evaluate(
								() => document.documentElement.scrollWidth <= innerWidth,
							),
							`${path}: no horizontal page overflow`,
						);
						assert.equal(
							await page.locator("button button, a button, button a").count(),
							0,
						);
						if (path === "/" && width === 390) {
							const sort = page.getByLabel("Sort by", { exact: true });
							await sort.selectOption("cost");
							assert.equal(await sort.inputValue(), "cost");
							const values = await page
								.locator(".card ol > li > div:last-child > span:first-child")
								.allTextContents();
							const prices = values.map((value) =>
								value === "Unknown"
									? Number.POSITIVE_INFINITY
									: Number(value.replace(/[$,]/g, "")),
							);
							assert.ok(
								prices.length > 0 &&
									prices.every((value) => !Number.isNaN(value)),
							);
							assert.deepEqual(
								prices,
								[...prices].sort((a, b) => a - b),
								"Phone cards follow the selected cost ordering",
							);
						}
						if (path === "/" && width === 1280) {
							const sort = page.locator("table").getByRole("button", {
								name: "Micro Brier",
								exact: true,
							});
							assert.ok(await sort.getAttribute("aria-describedby"));
							const header = sort.locator("xpath=ancestor::th");
							// Touch probes above legitimately sort the other columns.
							const expected =
								(await header.getAttribute("aria-sort")) === "ascending"
									? "descending"
									: "ascending";
							await sort.focus();
							await page.keyboard.press("Enter");
							assert.equal(
								await sort
									.locator("xpath=ancestor::th")
									.getAttribute("aria-sort"),
								expected,
							);
							await page.keyboard.press("Space");
							assert.equal(
								await sort
									.locator("xpath=ancestor::th")
									.getAttribute("aria-sort"),
								expected === "ascending" ? "descending" : "ascending",
							);
						}
					}
					assert.deepEqual(errors, [], "no console or hydration errors");
					await page.emulateMedia({ forcedColors: "active" });
					const trigger = page.locator("button[aria-describedby]").first();
					await trigger.focus();
					await page.keyboard.press("Tab");
					await page.keyboard.press("Shift+Tab");
					assert.ok(
						await trigger.evaluate((el) => el === document.activeElement),
					);
					assert.ok(
						await trigger.evaluate((el) => {
							const style = getComputedStyle(el);
							return (
								style.outlineStyle !== "none" &&
								Number.parseFloat(style.outlineWidth) >= 2
							);
						}),
						"Forced colors preserves a keyboard focus outline",
					);
					assert.ok(await page.getByRole("tooltip").first().isVisible());
					assert.equal(
						await page
							.getByRole("tooltip")
							.first()
							.evaluate((el) => getComputedStyle(el).transitionDuration),
						"0s",
					);
					await page.close();
				}
	} finally {
		await browser.close();
		await new Promise<void>((done, reject) =>
			server.close((error) => (error ? reject(error) : done())),
		);
	}
});
