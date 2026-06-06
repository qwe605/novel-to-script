import js from "@eslint/js";
import vuePlugin from "eslint-plugin-vue";

export default [
  js.configs.recommended,
  ...vuePlugin.configs["flat/essential"],
  {
    rules: {
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
      "no-console": "off",
      "vue/multi-word-component-names": "off",
      "vue/no-v-html": "off",
    },
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: "module",
      globals: {
        window: "readonly",
        document: "readonly",
        localStorage: "readonly",
        fetch: "readonly",
        FormData: "readonly",
        File: "readonly",
        Blob: "readonly",
        URL: "readonly",
        setTimeout: "readonly",
        clearInterval: "readonly",
        setInterval: "readonly",
        console: "readonly",
      },
    },
  },
];
