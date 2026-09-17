import { readFileSync } from "node:fs";
import { experimental_evaluate as evaluate } from "ai";

// One request, no repair loop: the provider's native probabilities are the
// benchmark output. Python owns durable attempts and spending reservations.
const request = JSON.parse(readFileSync(0, "utf8"));
if (request.model !== "typesafe-ai/jev") {
	throw new Error("This adapter only evaluates typesafe-ai/jev");
}
try {
	const result = await evaluate({
		...request,
		maxRetries: 0,
		abortSignal: AbortSignal.timeout(120_000),
	});
	process.stdout.write(
		JSON.stringify({
			answers: result.answers,
			usage: result.usage,
			warnings: result.warnings,
			providerMetadata: result.providerMetadata,
			// Gateway's response.modelId echoes the requested route; it is not proof of
			// a dated provider snapshot. Preserve routing evidence without inventing one.
			requestedModel: request.model,
		}),
	);
} catch (error) {
	process.stderr.write(
		JSON.stringify({
			error_name: error instanceof Error ? error.name : "UnknownError",
			status_code: Number.isInteger(error?.statusCode)
				? error.statusCode
				: null,
		}),
	);
	process.exitCode = 1;
}
