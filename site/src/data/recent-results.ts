import opus5 from "./exports/claude-opus-5.json" with { type: "json" };
import export2 from "./exports/claude-opus-5-5.json" with { type: "json" };
import sonnet5 from "./exports/claude-sonnet-5.json" with { type: "json" };
import export7 from "./exports/claude-sonnet-5-5.json" with { type: "json" };
import export5 from "./exports/gemini-3-1-pro-preview.json" with {
	type: "json",
};
import export4 from "./exports/gpt-4-1.json" with { type: "json" };
import export6 from "./exports/gpt-6-1-sol.json" with { type: "json" };
import export1 from "./exports/gpt-6-luna.json" with { type: "json" };
import export0 from "./exports/gpt-6-sol.json" with { type: "json" };
import export3 from "./exports/grok-4-7.json" with { type: "json" };
import { parseSiteExport } from "./site-export.js";

export const recentResults = [
	{
		source: {
			slug: "gpt-6-sol",
			release_date: "2026-09-22",
			forecast_run: "35776235829",
			scoring_run: "35885171489",
			access: "OpenAI API",
			display_name: "GPT-6 Sol",
			reasoning: "High",
			provider: "OpenAI",
			release: "cycle-1-91-2026-09-08-luna-r5",
			release_digest:
				"4311a6ee59c3ae1fcb392f1dd768ab00d1d7a7c7ea135271f3e117746233ed8a",
		},
		data: parseSiteExport(export0),
	},
	{
		source: {
			slug: "gpt-6-luna",
			release_date: "2026-09-22",
			forecast_run: "35933696453",
			scoring_run: "35940612024",
			access: "OpenAI API",
			display_name: "GPT-6 Luna",
			reasoning: "High",
			provider: "OpenAI",
			release: "cycle-1-91-2026-09-08-luna-r5",
			release_digest:
				"4311a6ee59c3ae1fcb392f1dd768ab00d1d7a7c7ea135271f3e117746233ed8a",
		},
		data: parseSiteExport(export1),
	},
	{
		source: {
			slug: "claude-opus-5-5",
			release_date: "2026-09-22",
			forecast_run: "35953489581",
			scoring_run: "35954306953",
			access: "Anthropic API",
			display_name: "Claude Opus 5.5",
			reasoning: "High",
			provider: "Anthropic",
			release: "cycle-1-91-2026-09-08-luna-r5",
			release_digest:
				"4311a6ee59c3ae1fcb392f1dd768ab00d1d7a7c7ea135271f3e117746233ed8a",
		},
		data: parseSiteExport(export2),
	},
	{
		source: {
			slug: "grok-4-7",
			release_date: "2026-09-21",
			forecast_run: "35799524684",
			scoring_run: "35885175070",
			access: "Vercel AI Gateway (served by xAI)",
			display_name: "Grok 4.7",
			reasoning: "High",
			provider: "SpaceXAI",
			release: "cycle-1-91-2026-09-08-luna-r5",
			release_digest:
				"4311a6ee59c3ae1fcb392f1dd768ab00d1d7a7c7ea135271f3e117746233ed8a",
		},
		data: parseSiteExport(export3),
	},
	{
		source: {
			slug: "gpt-4-1",
			release_date: "2025-04-14",
			forecast_run: "35954543028",
			scoring_run: "36073985227",
			access: "OpenAI API (dated snapshot gpt-4.1-2025-04-14)",
			display_name: "GPT-4.1",
			reasoning: "None (non-reasoning model)",
			provider: "OpenAI",
			release: "cycle-1-91-2026-09-08-luna-r5",
			release_digest:
				"4311a6ee59c3ae1fcb392f1dd768ab00d1d7a7c7ea135271f3e117746233ed8a",
		},
		data: parseSiteExport(export4),
	},
	{
		source: {
			slug: "gemini-3-1-pro-preview",
			release_date: "2026-02-19",
			forecast_run: "36075557088",
			scoring_run: "36169561374",
			access: "Google Gemini API (preview alias)",
			display_name: "Gemini 3.1 Pro Preview",
			reasoning: "High thinking",
			provider: "Google",
			release: "cycle-1-91-2026-09-08-luna-r5",
			release_digest:
				"4311a6ee59c3ae1fcb392f1dd768ab00d1d7a7c7ea135271f3e117746233ed8a",
		},
		data: parseSiteExport(export5),
	},
	{
		source: {
			slug: "gpt-6-1-sol",
			release_date: "2026-09-29",
			forecast_run: "36673524599",
			scoring_run: "36741462923",
			access: "OpenAI API",
			display_name: "GPT-6.1 Sol",
			reasoning: "High",
			provider: "OpenAI",
			release: "cycle-1-91-2026-09-08-luna-r5",
			release_digest:
				"4311a6ee59c3ae1fcb392f1dd768ab00d1d7a7c7ea135271f3e117746233ed8a",
		},
		data: parseSiteExport(export6),
	},
	{
		source: {
			slug: "claude-sonnet-5-5",
			release_date: "2026-09-28",
			forecast_run: "36673527185",
			scoring_run: "36741468019",
			access: "Anthropic API",
			display_name: "Claude Sonnet 5.5",
			reasoning: "High",
			provider: "Anthropic",
			release: "cycle-1-91-2026-09-08-luna-r5",
			release_digest:
				"4311a6ee59c3ae1fcb392f1dd768ab00d1d7a7c7ea135271f3e117746233ed8a",
		},
		data: parseSiteExport(export7),
	},
	{
		source: {
			slug: "claude-opus-5",
			release_date: "2026-07-24",
			forecast_run: "34845972981",
			scoring_run: "37143407387",
			access: "Anthropic API",
			display_name: "Claude Opus 5",
			reasoning: "Adaptive thinking (provider default: high)",
			provider: "Anthropic",
			release: "cycle-1-91-2026-09-08-luna-r5",
			release_digest:
				"4311a6ee59c3ae1fcb392f1dd768ab00d1d7a7c7ea135271f3e117746233ed8a",
		},
		data: parseSiteExport(opus5),
	},
	{
		source: {
			slug: "claude-sonnet-5",
			release_date: "2026-06-30",
			forecast_run: "34895753581",
			scoring_run: "37143409174",
			access: "Anthropic API",
			display_name: "Claude Sonnet 5",
			reasoning: "Adaptive thinking (provider default)",
			provider: "Anthropic",
			release: "cycle-1-91-2026-09-08-luna-r5",
			release_digest:
				"4311a6ee59c3ae1fcb392f1dd768ab00d1d7a7c7ea135271f3e117746233ed8a",
		},
		data: parseSiteExport(sonnet5),
	},
];
