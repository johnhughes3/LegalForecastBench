import { readFileSync } from "node:fs";
import { experimental_evaluate as evaluate } from "ai";

const MAX_ERROR_MESSAGE_LENGTH = 512;

function sanitizeErrorMessage(value, apiKey) {
	if (typeof value !== "string") {
		return "unknown provider error";
	}
	let message = value;
	if (apiKey) {
		message = message.split(apiKey).join("[REDACTED]");
	}
	message = message
		.replace(
			/\b(?:authorization|proxy-authorization)\s*[:=]?\s*["']?(?:bearer|basic|token)\s+[^\s,;"']+/gi,
			"[REDACTED_AUTHORIZATION]",
		)
		.replace(
			/\b(?:api[-_ ]?key|x-api-key|access[-_ ]?token|token|key)\s*[:=]\s*["']?[^\s,;}"']+/gi,
			"[REDACTED_KEY]",
		)
		.replace(/\p{Cc}/gu, " ")
		.trim();
	return message.slice(0, MAX_ERROR_MESSAGE_LENGTH) || "unknown provider error";
}

function safeGenerationId(value, apiKey) {
	if (
		typeof value !== "string" ||
		(apiKey && value.includes(apiKey)) ||
		!/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(value)
	) {
		return null;
	}
	return value;
}

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
	const apiKey = process.env.AI_GATEWAY_API_KEY ?? "";
	process.stderr.write(
		JSON.stringify({
			error_name: error instanceof Error ? error.name : "UnknownError",
			error_message: sanitizeErrorMessage(error?.message, apiKey),
			retryable: error?.isRetryable === true,
			status_code: Number.isInteger(error?.statusCode)
				? error.statusCode
				: null,
			generation_id: safeGenerationId(error?.generationId, apiKey),
		}),
	);
	process.exitCode = 1;
}
