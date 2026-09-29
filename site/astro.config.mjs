import mdx from "@astrojs/mdx";
import react from "@astrojs/react";
import sitemap from "@astrojs/sitemap";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "astro/config";

// Static output: Vercel serves dist/ directly, so no adapter or server runtime.
export default defineConfig({
	site: process.env.SITE_URL ?? "https://www.legalforecastbench.org",
	integrations: [react(), mdx(), sitemap()],
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
