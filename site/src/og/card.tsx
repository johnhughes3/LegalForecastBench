import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { Resvg } from "@resvg/resvg-js";
import type { ReactNode } from "react";
import satori from "satori";
import { OG_HEIGHT, OG_WIDTH } from "./routes";

/** Light-theme tokens from styles/global.css; previews always render light. */
const C = {
	bg: "#faf9f6",
	surface: "#ffffff",
	ink: "#17150f",
	ink2: "#4c483f",
	ink3: "#7a7569",
	rule: "#e3dfd5",
	accent: "#8a2432",
	accentSoft: "#f5e9e7",
};
const SERIF = "Newsreader";
const SANS = "Inter";

// Satori reads TTF/OTF/WOFF but not WOFF2, so the static @fontsource packages
// supply the same families the site loads as variable WOFF2.
const require = createRequire(import.meta.url);
const font = (pkg: string, file: string): Buffer =>
	readFileSync(require.resolve(`${pkg}/files/${file}`));
const fonts = [
	{
		name: SERIF,
		weight: 500,
		data: font("@fontsource/newsreader", "newsreader-latin-500-normal.woff"),
	},
	{
		name: SERIF,
		weight: 600,
		data: font("@fontsource/newsreader", "newsreader-latin-600-normal.woff"),
	},
	{
		name: SANS,
		weight: 400,
		data: font("@fontsource/inter", "inter-latin-400-normal.woff"),
	},
	{
		name: SANS,
		weight: 600,
		data: font("@fontsource/inter", "inter-latin-600-normal.woff"),
	},
] as const;

export interface LeaderRow {
	rank: number;
	name: string;
	value: string;
}

export type CardSpec =
	| { kind: "home"; title: string; cohort: string; leaders: LeaderRow[] }
	| { kind: "section"; eyebrow: string; title: string; cohort: string }
	| {
			kind: "model";
			name: string;
			qualifier: string | null;
			provider: string;
			brier: string;
			rank: number;
			total: number;
			cohort: string;
	  }
	| { kind: "finding"; kindLabel: string; title: string; cohort: string };

function Mark(): ReactNode {
	return (
		<svg width="44" height="44" viewBox="0 0 32 32" aria-hidden="true">
			<rect x="3" y="3" width="26" height="26" rx="7" fill={C.accent} />
			<path
				d="M10 21.5 14.5 16l3.2 3.2L23 11"
				fill="none"
				stroke={C.bg}
				strokeWidth="2.4"
				strokeLinecap="round"
				strokeLinejoin="round"
			/>
		</svg>
	);
}

function Frame({
	eyebrow,
	footer,
	host,
	children,
}: {
	eyebrow?: string;
	footer: string;
	host: string;
	children: ReactNode;
}): ReactNode {
	return (
		<div
			style={{
				width: OG_WIDTH,
				height: OG_HEIGHT,
				display: "flex",
				flexDirection: "column",
				background: C.bg,
				color: C.ink,
				fontFamily: SANS,
				padding: "56px 72px",
				borderTop: `12px solid ${C.accent}`,
			}}
		>
			<div style={{ display: "flex", alignItems: "center", gap: 16 }}>
				<Mark />
				<span style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 34 }}>
					LegalForecastBench
				</span>
				{eyebrow && (
					<span
						style={{
							marginLeft: "auto",
							fontSize: 20,
							fontWeight: 600,
							letterSpacing: 2.4,
							textTransform: "uppercase",
							color: C.accent,
						}}
					>
						{eyebrow}
					</span>
				)}
			</div>
			<div style={{ display: "flex", flex: 1, minHeight: 0 }}>{children}</div>
			<div
				style={{
					display: "flex",
					borderTop: `1px solid ${C.rule}`,
					paddingTop: 22,
					fontSize: 24,
					color: C.ink3,
				}}
			>
				<span>{footer}</span>
				<span style={{ marginLeft: "auto" }}>{host}</span>
			</div>
		</div>
	);
}

function Headline({
	children,
	size,
	lines,
}: {
	children: string;
	size: number;
	lines: number;
}): ReactNode {
	return (
		<div
			style={{
				display: "block",
				fontFamily: SERIF,
				fontWeight: 500,
				fontSize: size,
				lineHeight: 1.12,
				letterSpacing: -0.5,
				lineClamp: lines,
			}}
		>
			{children}
		</div>
	);
}

/** Shrink long headlines so they stay within the card. */
const headlineSize = (text: string, max: number): number =>
	text.length > 70
		? Math.round(max * 0.8)
		: text.length > 45
			? Math.round(max * 0.9)
			: max;

function Stat({ label, value }: { label: string; value: string }): ReactNode {
	return (
		<div
			style={{
				display: "flex",
				flexDirection: "column",
				borderLeft: `2px solid ${C.rule}`,
				paddingLeft: 24,
			}}
		>
			<span
				style={{
					fontFamily: SERIF,
					fontWeight: 500,
					fontSize: 64,
					lineHeight: 1,
				}}
			>
				{value}
			</span>
			<span style={{ marginTop: 10, fontSize: 24, color: C.ink2 }}>
				{label}
			</span>
		</div>
	);
}

function Body(spec: CardSpec): ReactNode {
	switch (spec.kind) {
		case "home":
			return (
				<div
					style={{
						display: "flex",
						flex: 1,
						gap: 56,
						alignItems: "center",
					}}
				>
					<div style={{ display: "flex", flex: 1 }}>
						<Headline size={58} lines={5}>
							{spec.title}
						</Headline>
					</div>
					<div
						style={{
							display: "flex",
							flexDirection: "column",
							width: 440,
							background: C.surface,
							border: `1px solid ${C.rule}`,
							borderRadius: 16,
							padding: "22px 28px",
						}}
					>
						<div
							style={{
								display: "flex",
								justifyContent: "space-between",
								fontSize: 17,
								fontWeight: 600,
								letterSpacing: 1.6,
								textTransform: "uppercase",
								color: C.accent,
								paddingBottom: 10,
							}}
						>
							<span>Top models</span>
							<span>Micro Brier</span>
						</div>
						{spec.leaders.map((row) => (
							<div
								key={row.name}
								style={{
									display: "flex",
									alignItems: "center",
									borderTop: `1px solid ${C.rule}`,
									padding: "11px 0",
									fontSize: 24,
								}}
							>
								<span style={{ width: 34, color: C.ink3 }}>{row.rank}</span>
								<span style={{ flex: 1, fontWeight: 600 }}>{row.name}</span>
								<span style={{ color: C.ink2 }}>{row.value}</span>
							</div>
						))}
					</div>
				</div>
			);
		case "section":
		case "finding": {
			const title = spec.title;
			return (
				<div
					style={{
						display: "flex",
						flex: 1,
						alignItems: "center",
						paddingRight: 80,
					}}
				>
					<Headline size={headlineSize(title, 72)} lines={4}>
						{title}
					</Headline>
				</div>
			);
		}
		case "model":
			return (
				<div
					style={{
						display: "flex",
						flexDirection: "column",
						flex: 1,
						justifyContent: "center",
					}}
				>
					<span style={{ fontSize: 28, color: C.ink2 }}>
						{spec.qualifier
							? `${spec.provider} · ${spec.qualifier}`
							: spec.provider}
					</span>
					<div style={{ display: "flex", marginTop: 6 }}>
						<Headline size={spec.name.length > 20 ? 68 : 84} lines={2}>
							{spec.name}
						</Headline>
					</div>
					<div style={{ display: "flex", gap: 64, marginTop: 44 }}>
						<Stat label="Micro Brier (lower is better)" value={spec.brier} />
						<Stat
							label={`Rank of ${spec.total} models`}
							value={`#${spec.rank}`}
						/>
					</div>
				</div>
			);
	}
}

const eyebrowOf = (spec: CardSpec): string | undefined =>
	spec.kind === "section"
		? spec.eyebrow
		: spec.kind === "finding"
			? spec.kindLabel
			: spec.kind === "model"
				? "Model"
				: undefined;

export async function renderCard(
	spec: CardSpec,
	host: string,
): Promise<Uint8Array<ArrayBuffer>> {
	const eyebrow = eyebrowOf(spec);
	const svg = await satori(
		<Frame footer={spec.cohort} host={host} {...(eyebrow ? { eyebrow } : {})}>
			{Body(spec)}
		</Frame>,
		{ width: OG_WIDTH, height: OG_HEIGHT, fonts: [...fonts] },
	);
	const png = new Resvg(svg, {
		fitTo: { mode: "width", value: OG_WIDTH },
	})
		.render()
		.asPng();
	return new Uint8Array(png);
}
