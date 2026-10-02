import { execSync } from "node:child_process";
import { resolve } from "node:path";

const REPO = resolve(import.meta.dirname, "../..");
const HEALTH = "http://localhost:8001/api/health";

function run(command: string): void {
  execSync(command, { cwd: REPO, stdio: "inherit" });
}

async function waitForApi(timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      if ((await fetch(HEALTH)).ok) return;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`API do testów e2e nie odpowiada pod ${HEALTH}.`);
}

/** A fresh database (tmpfs) and API instance for every run, and the synthetic XTB export. */
export default async function globalSetup(): Promise<void> {
  run("docker compose --profile e2e rm -sf db-e2e api-e2e"); // leftovers of an interrupted run
  run("docker compose --profile e2e up -d --build db-e2e api-e2e");
  await waitForApi(120_000);
  run("docker compose --profile e2e exec -T api-e2e python -m tests.e2e_fixture");
}
