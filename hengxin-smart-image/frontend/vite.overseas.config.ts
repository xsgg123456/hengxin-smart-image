import { mergeConfig } from "vite";
import baseConfig from "./vite.config";
import path from "node:path";

// 复用一期编译配置；此入口只构建模拟预览，不代理任何真实 API。
export default () =>
  mergeConfig(baseConfig({ mode: "demo", isolatedPreview: true }), {
    define: { "import.meta.env.VITE_ISOLATED_PREVIEW": JSON.stringify("true") },
    server: { port: 3012, proxy: undefined },
    build: {
      outDir: "dist-overseas",
      rollupOptions: {
        input: {
          overseas: path.resolve("overseas-preview.html"),
          domestic: path.resolve("index.html"),
        },
      },
    },
  });
