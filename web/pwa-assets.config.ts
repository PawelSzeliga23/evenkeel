import { defineConfig, minimal2023Preset as preset } from "@vite-pwa/assets-generator/config";

const background = { background: "#0E1116" };

export default defineConfig({
  headLinkOptions: { preset: "2023" },
  preset: {
    ...preset,
    maskable: { ...preset.maskable, resizeOptions: background },
    apple: { ...preset.apple, resizeOptions: background },
  },
  images: ["public/icon.svg"],
});
