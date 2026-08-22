// SPDX-FileCopyrightText: 2026 Alexander Gomez
// SPDX-License-Identifier: GPL-3.0-or-later
//
// The npm licence gate of ADR 0021 decision 4 (roadmap W0).
//
//     node scripts/check-licences.mjs [path/to/package-lock.json]
//
// Reads the COMMITTED lockfile -- not `node_modules/`, not the registry -- so
// the gate is offline, deterministic, and answers the question a reviewer
// actually asks: what does this repository commit its users to installing?
// Every package in the tree is checked, dev and optional alike (see the header
// of licence-policy.mjs for why there is no exemption).
//
// Exit status: 0 clean, 1 policy violation, 2 the gate itself could not run
// (missing or unreadable lockfile). Distinguishing 2 from 1 matters -- a gate
// that cannot read its input has not passed, and must not look like a pass.
//
// The optional path argument exists for the NEGATIVE test roadmap W0 requires:
// a tampered copy of the lock with an AGPL-3.0 package in it, run through this
// script, its exact output recorded. Without the argument the negative test
// would have to write into the real lockfile.
// ----------------------------------------------------------------------------

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { ALLOWED, auditLock } from './licence-policy.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const lockPath = resolve(process.argv[2] ?? resolve(here, '..', 'package-lock.json'));

/** @type {Record<string, unknown>} */
let lock;
try {
  lock = JSON.parse(readFileSync(lockPath, 'utf8'));
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`licence gate: cannot read ${lockPath}: ${message}`);
  console.error('The gate has not passed -- it did not run. Exit 2.');
  process.exit(2);
}

const report = auditLock(lock);

console.log(`licence gate (ADR 0021 decision 4) over ${lockPath}`);
console.log(`  allowlist: ${[...ALLOWED].join(', ')}`);
console.log(`  packages scanned: ${report.scanned}${report.skipped > 0 ? ` (+${report.skipped} workspace links skipped)` : ''}`);

// The root package is not a dependency and is not governed by the allowlist,
// but a root that stopped declaring GPL-3.0-or-later would be an ADR 0004
// boundary break -- so it is reported, and it is fatal.
let rootBroken = false;
if (report.rootLicence === 'GPL-3.0-or-later') {
  console.log('  root package: GPL-3.0-or-later (ADR 0004 item 2) — ok');
} else {
  console.error(
    `  root package: declares ${report.rootLicence ?? '<absent>'} — everything under host/ is ` +
      'GPL-3.0-or-later (ADR 0004 item 2, ADR 0021 decision 4)',
  );
  rootBroken = true;
}

const counts = [...report.counts.entries()].sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0]));
for (const [licence, count] of counts) {
  console.log(`  ${String(count).padStart(4)}  ${licence}`);
}

if (report.violations.length > 0) {
  console.error('');
  console.error(`licence gate FAILED: ${report.violations.length} package(s) refused.`);
  for (const violation of report.violations) {
    console.error('');
    console.error(`  ${violation.name}@${violation.version}  [${violation.reason}]`);
    console.error(`    path:    ${violation.path}`);
    console.error(`    licence: ${violation.licence}`);
    console.error(`    ${violation.note}`);
  }
  console.error('');
  console.error(
    'The allowlist is a POLICY (ADR 0021 decision 4) and widening it is the owner\'s decision ' +
      '(roadmap W0). Remove or replace the dependency; do not edit ALLOWED to make this pass.',
  );
  process.exit(1);
}

if (rootBroken) {
  process.exit(1);
}

console.log('licence gate: clean — every package on the allowlist.');
