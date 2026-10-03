import { fileURLToPath } from "node:url";
import mdx from "@astrojs/mdx";
import react from "@astrojs/react";
import sitemap from "@astrojs/sitemap";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "astro/config";
import {
	copyRefreshedDownloads,
	refreshedDataDirectory,
} from "./src/data/dataset-input.ts";
import { SITE_ORIGIN } from "./src/seo/identity.ts";
import { includeInSitemap, withLastmod } from "./src/seo/sitemap.ts";

// Static output: Vercel serves dist/ directly, so no adapter or server runtime.
export default defineConfig({
	site: SITE_ORIGIN,
	trailingSlash: "always",
	integrations: [
		{
			name: "refreshed-public-data",
			hooks: {
				"astro:build:done": ({ dir }) => {
					if (refreshedDataDirectory)
						copyRefreshedDownloads(
							refreshedDataDirectory,
							fileURLToPath(new URL("data/", dir)),
						);
				},
			},
		},
		react(),
		mdx(),
		sitemap({
			filter: includeInSitemap,
			serialize: withLastmod,
		}),
	],
	// The Findings and Experiments indexes merged into /analysis/; their
	// articles keep their URLs.
	redirects: {
		"/findings": "/analysis/",
		"/experiments": "/analysis/",
	},
	vite: {
		plugins: [tailwindcss()],
		// The methods page renders docs/METHODS.md from the repository root.
		server: { fs: { allow: [".."] } },
	},
});
