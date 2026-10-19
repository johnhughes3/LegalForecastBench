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

    const documentDescriptor = api.pluginConfig.documentDescriptor;
    if (documentDescriptor !== undefined
      && (!Number.isInteger(documentDescriptor) || documentDescriptor < 3)) {
      throw new Error("Invalid release document tool descriptor");
    }

    function readDescriptor(fd, request) {
      writeSync(fd, Buffer.from(JSON.stringify(request) + '\n'));
      const parts = [];
      let bytes = 0;
      while (bytes <= 1048576) {
        const chunk = Buffer.alloc(4096);
        const count = readSync(fd, chunk, 0, chunk.length, null);
        if (!count) throw new Error("Host container tool channel closed");
        const part = chunk.subarray(0, count);
        parts.push(part);
        bytes += count;
        if (part.includes(10)) break;
      }
      if (bytes > 1048576) throw new Error("Host tool response too large");
      return JSON.parse(Buffer.concat(parts).toString("utf8"));
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
        const response = readDescriptor(descriptor, {page: args.page, receipt: args.receipt});
        if (typeof response.text !== "string") throw new Error("Host container read failed");
        return { content: [{ type: "text", text: response.text }] };
      },
    });

    if (documentDescriptor !== undefined) {
      api.registerTool({
        name: "lfb_read_release_document",
        description: "Read the authenticated release-document catalog or one bounded document page. Read the catalog first, then each document from offset 0 until complete.",
        parameters: {
          type: "object",
          properties: {
            path: { type: "string", minLength: 1, maxLength: 512 },
            offset: { type: "integer", minimum: 0 },
          },
          additionalProperties: false,
        },
        async execute(_id, args) {
          if (!args || typeof args !== "object" || Array.isArray(args)
            || Object.keys(args).some(key => !["path", "offset"].includes(key))) {
            throw new Error("Release document tool arguments are invalid");
          }
          if (args.path !== undefined
            && (typeof args.path !== "string" || args.path.length === 0 || args.path.length > 512)) {
            throw new Error("Release document path is invalid");
          }
          if (args.offset !== undefined
            && (!Number.isInteger(args.offset) || args.offset < 0)) {
            throw new Error("Release document offset is invalid");
          }
          const request = {offset: args.offset ?? 0};
          if (args.path !== undefined) request.path = args.path;
          const response = readDescriptor(documentDescriptor, request);
          if (typeof response.text !== "string") throw new Error("Host document read failed");
          return { content: [{ type: "text", text: response.text }] };
        },
      });
    }
  },
};
