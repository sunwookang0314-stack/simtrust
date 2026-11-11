import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "./": GitHub Pages 하위 경로(/simtrust/web/)에서도 파일을 찾게 상대 경로로 빌드한다
export default defineConfig({
  plugins: [react()],
  base: "./",
});
