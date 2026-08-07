import { defineConfig } from "vitepress";

export default defineConfig({
  title: "NeuLitTrace",
  description: "Rare-case literature retrieval with Snowflake cost measurement and EverMind memory.",
  head: [["link", { rel: "icon", href: "/favicon.ico" }]],
  markdown: { math: true },
  srcExclude: ["superpowers/**", "design-references/**", "backend-retrieval-improvements.md", "summary-tabs-restructure.md"],
  themeConfig: {
    logo: "/logo-n.svg",
    nav: [
      { text: "Overview", link: "/overview" },
      { text: "Architecture", link: "/architecture" },
      { text: "Token economy", link: "/token-economy" },
      { text: "Memory", link: "/memory" },
      { text: "API", link: "/api-reference" },
    ],
    sidebar: [
      { text: "Introduction", items: [
        { text: "Overview", link: "/overview" },
        { text: "Migration from v1", link: "/migration-from-v1" },
      ] },
      { text: "Architecture", items: [
        { text: "Component map", link: "/architecture" },
        { text: "Inference", link: "/architecture-inference" },
        { text: "Token economy", link: "/token-economy" },
        { text: "EverMind memory", link: "/memory" },
      ] },
      { text: "Data and API", items: [
        { text: "Corpus model", link: "/data-model-corpus" },
        { text: "Contract schemas", link: "/data-model-schemas" },
        { text: "API reference", link: "/api-reference" },
      ] },
    ],
  },
});
