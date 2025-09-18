// @ts-check
import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import react from "@astrojs/react";

// https://astro.build/config
export default defineConfig({
  site: "https://chunkhound.github.io",
  base: "/",
  integrations: [
    react(),
    starlight({
      title: "ChunkHound",
      description:
        "Modern RAG for your codebase - semantic and regex search via MCP",
      logo: {
        light: "./public/wordmark.svg",
        dark: "./public/wordmark-dark.svg",
        replacesTitle: true,
      },
      favicon: "/favicon.svg",
      customCss: ["./src/styles/colors.css", "./src/styles/changelog.css"],
      expressiveCode: {
        themes: ["github-light", "github-dark"],
      },
      social: [
        {
          icon: "github",
          label: "GitHub",
          href: "https://github.com/chunkhound/chunkhound",
        },
      ],
      sidebar: [
        { label: "Tutorial", slug: "tutorial" },
        { label: "Configuration", slug: "configuration" },
        { label: "Code Expert Agent", slug: "code-expert-agent" },
        { label: "Under the Hood", slug: "under-the-hood" },
        { label: "Origin Story", slug: "origin-story" },
        { label: "Changelog", link: "/changelog" },
      ],
    }),
  ],
});
