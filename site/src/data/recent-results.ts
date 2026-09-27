import export2 from "./exports/claude-opus-5-5.json" with { type: "json" };
import export5 from "./exports/gemini-3-1-pro-preview.json" with {
	type: "json",
};
import export4 from "./exports/gpt-4-1.json" with { type: "json" };
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
			training_cutoff: "April 20, 2026 (knowledge cutoff)",
			eligibility_reason:
				"OpenAI reports an April 20, 2026 knowledge cutoff but has not documented a training-data cutoff, so eligibility cannot be established.",
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
			training_cutoff: "May 18, 2026 (knowledge cutoff)",
			eligibility_reason:
				"OpenAI reports a May 18, 2026 knowledge cutoff but has not documented a training-data cutoff, so eligibility cannot be established.",
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
			training_cutoff: "June 2026",
			eligibility_reason:
				"Anthropic reports a June 2026 training-data cutoff without a day, which overlaps the earliest June 30 decision.",
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
			training_cutoff: "May 2026 (knowledge cutoff)",
			eligibility_reason:
				"xAI reports a May 2026 knowledge cutoff but has not documented a training-data cutoff, so eligibility cannot be established.",
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
			training_cutoff: "June 1, 2024 (knowledge cutoff)",
			eligibility_reason:
				"OpenAI reports a June 1, 2024 knowledge cutoff but has not documented a training-data cutoff, so eligibility cannot be established.",
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
			training_cutoff: "January 2025 (knowledge cutoff)",
			eligibility_reason:
				"Google reports a January 2025 knowledge cutoff but has not documented a training-data cutoff, so eligibility cannot be established.",
			provider: "Google",
			release: "cycle-1-91-2026-09-08-luna-r5",
			release_digest:
				"4311a6ee59c3ae1fcb392f1dd768ab00d1d7a7c7ea135271f3e117746233ed8a",
		},
		data: parseSiteExport(export5),
	},
];
