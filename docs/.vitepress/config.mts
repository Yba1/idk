import { defineConfig } from "vitepress";

export default defineConfig({
  title: "NeuLitTrace",
  description: "RAG tool for rare PET and neuroimaging findings, built for Paritok's Token-Efficiency Hackathon.",
  head: [["link", { rel: "icon", href: "/favicon.ico" }]],
  markdown: {
    math: true,
  },
  srcExclude: [
    "superpowers/**",
    "design-references/**",
    "backend-retrieval-improvements.md",
    "summary-tabs-restructure.md",
  ],
  themeConfig: {
    logo: "/logo-n.svg",
    nav: [
      { text: "Overview", link: "/overview" },
      { text: "Architecture", link: "/architecture" },
      { text: "Why Paritok", link: "/why-paritok" },
      { text: "API Reference", link: "/api-reference" },
    ],
    sidebar: [
      {
        text: "📖 Introduction",
        items: [{ text: "Overview & Quickstart", link: "/overview" }],
      },
      {
        text: "🧠 Backend & Pipeline",
        items: [
          { text: "Architecture", link: "/architecture" },
          { text: "LLM Egress Paths", link: "/architecture-llm-paths" },
          { text: "Search Loop", link: "/search-loop" },
        ],
      },
      {
        text: "🤝 Paritok",
        items: [
          { text: "Why Paritok", link: "/why-paritok" },
          { text: "Integration & Measured Numbers", link: "/paritok-integration" },
          { text: "Hackathon Feedback", link: "/paritok-feedback" },
        ],
      },
      {
        text: "🗂️ Data & API",
        items: [
          { text: "Data Model: Corpus Records", link: "/data-model-corpus" },
          { text: "Data Model: API Schemas", link: "/data-model-schemas" },
          { text: "API Reference", link: "/api-reference" },
        ],
      },
    ],
  },
});
