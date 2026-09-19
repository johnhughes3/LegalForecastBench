import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const integrationDirectory = dirname(fileURLToPath(import.meta.url));
const evaluateScript = resolve(integrationDirectory, "evaluate.mjs");

test("native SDK gateway diagnostics are bounded and do not retry", () => {
	const apiKey = "fixture-gateway-key";
	const harness = `
let fetchCalls = 0;
globalThis.fetch = async () => {
  fetchCalls += 1;
  return new Response(JSON.stringify({
      error: {
        type: "internal_server_error",
      message: ("backend failed\\nAuthorization: Bearer ${apiKey}; apiKey=${apiKey}\\u0000" + "x".repeat(1000)),
    },
    generationId: "gen_fixture_789",
  }), {
    status: 500,
    headers: { "content-type": "application/json" },
  });
};
await import(${JSON.stringify(pathToFileURL(evaluateScript).href)});
process.stdout.write(JSON.stringify({ fetch_calls: fetchCalls }));
`;
	const result = spawnSync(
		process.execPath,
		["--input-type=module", "--eval", harness],
		{
			cwd: integrationDirectory,
			encoding: "utf8",
			env: {
				PATH: process.env.PATH,
				AI_GATEWAY_API_KEY: apiKey,
			},
			input: JSON.stringify({
				model: "typesafe-ai/jev",
				state: { request_marker: "must-not-appear-in-diagnostics" },
				questions: {
					unit_fixture: {
						type: "boolean",
						instructions: "Is the claim supported?",
					},
				},
			}),
			timeout: 10_000,
		},
	);

	assert.equal(result.status, 1, result.stderr);
	const diagnostics = JSON.parse(result.stderr);
	const harnessResult = JSON.parse(result.stdout);
	assert.equal(harnessResult.fetch_calls, 1);
	assert.equal(diagnostics.error_name, "GatewayInternalServerError");
	assert.equal(diagnostics.status_code, 500);
	assert.equal(diagnostics.retryable, true);
	assert.equal(diagnostics.generation_id, "gen_fixture_789");
	assert.match(diagnostics.error_message, /backend failed/);
	assert.doesNotMatch(diagnostics.error_message, /fixture-gateway-key/);
	assert.doesNotMatch(diagnostics.error_message, /Authorization: Bearer/);
	assert.doesNotMatch(diagnostics.error_message, /apiKey=/);
	assert.doesNotMatch(diagnostics.error_message, /\p{Cc}/u);
	assert.ok(diagnostics.error_message.length <= 512);
	assert.doesNotMatch(result.stderr, /must-not-appear-in-diagnostics/);
});
