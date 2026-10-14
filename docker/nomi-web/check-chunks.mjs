#!/usr/bin/env node
/**
 * Authoritative syntax gate for the NOMI web image.
 *
 * The rebrand rewrites upstream bundles with text substitutions; a mistake
 * (e.g. deleting an object key instead of its text) produces invalid JS that
 * surfaces only as a blank page in production. This script copies the built
 * image's asset directory and parses EVERY bundle as an ES module, so a broken
 * chunk fails before deploy instead of in the browser.
 *
 * Usage: node docker/nomi-web/check-chunks.mjs [image]   (default pmo-web:latest)
 */
import { execFileSync } from "node:child_process";
import { cpSync, mkdtempSync, rmSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const image = process.argv[2] ?? "pmo-web:latest";
const assetDir = "/usr/share/nginx/html/assets-nomi";
const env = { ...process.env, MSYS_NO_PATHCONV: "1" };

const workdir = mkdtempSync(join(tmpdir(), "nomi-gate-"));
let failures = 0;
let checked = 0;

try {
  const container = execFileSync("docker", ["create", image], { encoding: "utf8", env }).trim();
  try {
    execFileSync("docker", ["cp", `${container}:${assetDir}`, join(workdir, "assets")], { stdio: "pipe", env });
  } finally {
    execFileSync("docker", ["rm", "-f", container], { stdio: "pipe", env });
  }

  const dir = join(workdir, "assets");
  const bundles = readdirSync(dir).filter((f) => f.endsWith(".js"));
  if (!bundles.length) {
    console.error(`no bundles found at ${assetDir} in ${image}`);
    process.exit(1);
  }

  for (const name of bundles) {
    checked += 1;
    try {
      // --check parses without executing: no side effects, no import resolution.
      execFileSync(process.execPath, ["--check", join(dir, name)], { stdio: "pipe" });
    } catch (error) {
      failures += 1;
      const detail = (error.stderr?.toString() || error.message || "").split("\n").slice(0, 4).join("\n");
      console.error(`SYNTAX FAIL ${name}:\n${detail}`);
    }
  }
} finally {
  rmSync(workdir, { recursive: true, force: true });
}

if (failures) {
  console.error(`\n${failures} of ${checked} bundles failed to parse — DO NOT DEPLOY`);
  process.exit(1);
}
console.log(`all ${checked} bundles parse cleanly (${image})`);
