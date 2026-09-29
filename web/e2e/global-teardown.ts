import { execSync } from "node:child_process";
import { resolve } from "node:path";

export default function globalTeardown(): void {
  execSync("docker compose --profile e2e rm -sf db-e2e api-e2e", { cwd: resolve(import.meta.dirname, "../.."), stdio: "inherit" });
}
