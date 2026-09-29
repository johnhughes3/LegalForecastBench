/** @jsxRuntime automatic */
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { Resvg } from "@resvg/resvg-js";
import satori from "satori";
import { BRAND_BURGUNDY, COURTHOUSE_PATH } from "../src/brand";

const require = createRequire(import.meta.url);
const root = new URL("../public/", import.meta.url);
const save = (name: string, data: string | Buffer): void =>
	writeFileSync(new URL(name, root), data);
const svg = (body: string, box = "0 0 32 35"): string =>
	`<svg xmlns="http://www.w3.org/2000/svg" viewBox="${box}" role="img"><title>LegalForecastBench</title>${body}</svg>\n`;
const mark = `<path fill="${BRAND_BURGUNDY}" d="${COURTHOUSE_PATH}"/>`;
save("brand/courthouse.svg", svg(mark));
save(
	"brand/courthouse-reversed.svg",
	svg(mark.replace(BRAND_BURGUNDY, "#faf9f6")),
);
const favicon = svg(
	`<rect width="40" height="40" rx="7" fill="#faf9f6"/><g transform="translate(4 2.5)">${mark}</g>`,
	"0 0 40 40",
);
save("favicon.svg", favicon);
const raster = (source: string, width: number): Buffer =>
	new Resvg(source, { fitTo: { mode: "width", value: width } })
		.render()
		.asPng();
save("favicon-32.png", raster(favicon, 32));
save(
	"apple-touch-icon.png",
	raster(
		svg(
			`<rect width="48" height="48" fill="#faf9f6"/><g transform="translate(8 6.5)">${mark}</g>`,
			"0 0 48 48",
		),
		180,
	),
);
const sizes = [16, 32, 48];
const images = sizes.map((size) => raster(favicon, size));
const header = Buffer.alloc(6 + 16 * sizes.length);
header.writeUInt16LE(1, 2);
header.writeUInt16LE(sizes.length, 4);
let offset = header.length;
images.forEach((png, i) => {
	const entry = 6 + 16 * i;
	header[entry] = sizes[i];
	header[entry + 1] = sizes[i];
	header.writeUInt16LE(1, entry + 4);
	header.writeUInt16LE(32, entry + 6);
	header.writeUInt32LE(png.length, entry + 8);
	header.writeUInt32LE(offset, entry + 12);
	offset += png.length;
});
save("favicon.ico", Buffer.concat([header, ...images]));
const lq = readFileSync(new URL("brand/legalquants.svg", root));
const fonts = [
	{
		name: "Newsreader",
		weight: 500 as const,
		data: readFileSync(
			require.resolve(
				"@fontsource/newsreader/files/newsreader-latin-500-normal.woff",
			),
		),
	},
	{
		name: "Inter",
		weight: 400 as const,
		data: readFileSync(
			require.resolve("@fontsource/inter/files/inter-latin-400-normal.woff"),
		),
	},
];
for (const partnership of [false, true]) {
	for (const reversed of [false, true]) {
		const ink = reversed ? "#faf9f6" : "#17150f";
		const logo = await satori(
			<div
				style={{
					display: "flex",
					alignItems: "flex-start",
					padding: "20px",
					gap: 26,
					width: "100%",
					height: "100%",
				}}
			>
				<svg width="72" height="79" viewBox="0 0 32 35" aria-hidden="true">
					<path fill={reversed ? ink : BRAND_BURGUNDY} d={COURTHOUSE_PATH} />
				</svg>
				<div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
					<div
						style={{
							fontFamily: "Newsreader",
							fontWeight: 500,
							fontSize: 72,
							lineHeight: 1.15,
							color: ink,
							letterSpacing: "-1.8px",
						}}
					>
						LegalForecastBench
					</div>
					{partnership && (
						<div
							style={{
								display: "flex",
								alignItems: "center",
								gap: 22,
								fontFamily: "Inter",
								fontSize: 24,
								color: reversed ? ink : "#4c483f",
							}}
						>
							<span>In partnership with LegalQuants</span>
							<img
								src={`data:image/svg+xml;base64,${lq.toString("base64")}`}
								width={40}
								height={40}
								alt=""
							/>
						</div>
					)}
				</div>
			</div>,
			{ width: 780, height: partnership ? 160 : 120, fonts, embedFont: true },
		);
		const name = `brand/${partnership ? "partnership" : "wordmark"}${reversed ? "-reversed" : ""}.svg`;
		save(
			name,
			logo
				.replace(/<svg\b/, '<svg role="img"')
				.replace(
					/(<svg[^>]*>)/,
					"$1<title>LegalForecastBench" +
						(partnership ? " — In partnership with LegalQuants" : "") +
						"</title>",
				),
		);
	}
}
