import { readSync, writeSync } from "node:fs";

// The descriptor is a private inherited socket, not a network endpoint or a path
// supplied by the model. OpenClaw owns all model turns; this tool only does RPC.
export default {
  id: "lfb-container-tool",
  register(api) {
    const descriptor = api.pluginConfig.descriptor;
    if (!Number.isInteger(descriptor) || descriptor < 3) {
      throw new Error("Missing host container tool descriptor");
    }
    api.registerTool({
      name: "lfb_read_task",
      description: "Read all staged task pages in order. Start page=0, receipt=''. Echo each next_page and receipt until complete=true before forecasting.",
      parameters: {
        type: "object",
        properties: { page: { type: "integer", minimum: 0 }, receipt: { type: "string" } },
        required: ["page", "receipt"],
        additionalProperties: false,
      },
      async execute(_id, args) {
        if (!args || Object.keys(args).length !== 2 || !Number.isInteger(args.page)
          || args.page < 0 || typeof args.receipt !== "string" || args.receipt.length > 32) {
          throw new Error("Solver prompt tool requires a page and prior receipt");
        }
        writeSync(descriptor, Buffer.from(JSON.stringify({page: args.page, receipt: args.receipt}) + '\n'));
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
        if (typeof response.text !== "string") throw new Error("Host container read failed");
        return { content: [{ type: "text", text: response.text }] };
      },
    });
  },
};
