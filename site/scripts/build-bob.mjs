// Build the copy that Bob serves at /website (then run bob/tools/import_website.py).
// A tiny script instead of an inline env var so it works the same in PowerShell, cmd and bash.
import { spawnSync } from "node:child_process";

const result = spawnSync("npx", ["next", "build"], {
  stdio: "inherit",
  shell: true,
  env: { ...process.env, SITE_BASE_PATH: "/website" },
});
process.exit(result.status ?? 1);
