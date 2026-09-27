import { readSync, writeSync } from "node:fs";

// The descriptor is a private inherited socket, not a network endpoint or a path
// supplied by the model. OpenClaw owns all model turns; this tool only does RPC.
export default {
  id: "lfb-container-tool",
  register(api) {
    let used = false;
    const descriptor = api.pluginConfig.descriptor;
    if (!Number.isInteger(descriptor) || descriptor < 3) {
      throw new Error("Missing host container tool descriptor");
    }
    api.registerTool({
      name: "lfb_read_task",
      description: "Read the complete, host-staged LegalForecastBench solver prompt.",
      parameters: { type: "object", properties: {}, additionalProperties: false },
      async execute(_id, args) {
        if (used || !args || Object.keys(args).length !== 0) {
          throw new Error("Solver prompt tool accepts one call with no arguments");
        }
        used = true;
        writeSync(descriptor, Buffer.from('{"operation":"read_solver_prompt"}\n'));
        const parts = [];
        let bytes = 0;
        while (bytes <= 1048576) {
          const chunk = Buffer.alloc(4096);
          const count = readSync(descriptor, chunk, 0, chunk.length, null);
          if (!count) throw new Error("Host container tool channel closed");
          const part = chunk.subarray(0, count);
          parts.push(part);
          bytes += count;
          if (part.includes(10)) break;
        }
        if (bytes > 1048576) throw new Error("Host tool response too large");
        const response = JSON.parse(Buffer.concat(parts).toString("utf8"));
        if (response.status !== "succeeded") throw new Error("Host container read failed");
        return { content: [{ type: "text", text: JSON.stringify(response.output) }] };
      },
    });
  },
};
