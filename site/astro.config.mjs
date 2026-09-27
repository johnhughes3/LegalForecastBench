import mdx from "@astrojs/mdx";
import react from "@astrojs/react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "astro/config";

// Static output: Vercel serves dist/ directly, so no adapter or server runtime.
export default defineConfig({
	site: process.env.SITE_URL ?? "https://legalforecastbench.vercel.app",
	integrations: [react(), mdx()],
	vite: {
		plugins: [tailwindcss()],
		// The methods page renders docs/METHODS.md from the repository root.
		server: { fs: { allow: [".."] } },
	},
});
