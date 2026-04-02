import fs from 'node:fs/promises';

export default async function globalSetup() {
  const targets = [
    process.env.ORBITAL_INSPECT_E2E_ROOT,
    process.env.ORBITAL_INSPECT_E2E_DB_PATH,
    process.env.ORBITAL_INSPECT_E2E_UPLOADS_PATH,
  ].filter(Boolean) as string[];

  await Promise.all(
    targets.map((target) => fs.rm(target, { recursive: true, force: true }))
  );
}
