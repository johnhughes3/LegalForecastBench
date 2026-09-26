import { Ajv2020 } from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import schema from "../../../docs/schemas/site-export-v1.schema.json" with {
	type: "json",
};
import type { SiteExport } from "../generated/site-export.js";

export type { SiteExport } from "../generated/site-export.js";

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validate = ajv.compile<SiteExport>(schema);

/** Validate at the data boundary before components consume a public export. */
export function parseSiteExport(value: unknown): SiteExport {
	if (!validate(value)) {
		throw new Error(
			`Invalid site export: ${ajv.errorsText(validate.errors, { separator: "; " })}`,
		);
	}
	return value;
}
