// SPDX-FileCopyrightText: 2026 Alexander Gomez
// SPDX-License-Identifier: GPL-3.0-or-later
//
// The npm licence gate's own tests (ADR 0021 decision 4, roadmap W0).
//
// Two kinds of test live here and they are not interchangeable:
//   * POLICY tests over hand-built lockfiles — including the AGPL-3.0 negative
//     case roadmap W0's definition of done names, which cannot be run against
//     the real lock without actually installing an AGPL package.
//   * One test over the COMMITTED package-lock.json, so a dependency bump that
//     drags in an unlisted licence turns this suite red in CI before anyone
//     looks at the gate's own exit status.
// ----------------------------------------------------------------------------

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { ALLOWED, NAMED_REFUSALS, auditLock, evaluateExpression } from '../../scripts/licence-policy.mjs';

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');

/** Minimal lockfile shell; tests add the packages they care about. */
function lockWith(packages: Record<string, Record<string, unknown>>): Record<string, unknown> {
  return {
    name: 'superspectral-web',
    lockfileVersion: 3,
    requires: true,
    packages: {
      '': { name: 'superspectral-web', version: '0.0.0', license: 'GPL-3.0-or-later' },
      ...packages,
    },
  };
}

describe('the allowlist is the policy, verbatim', () => {
  // This test exists to make widening the allowlist a VISIBLE act. Roadmap W0:
  // "Alexander approves the npm allowlist — the licence list of ADR 0021
  // decision 4 is a policy, not a lockfile, and it is his to sign." An agent
  // that adds a row to make a build pass has to delete a test that says why.
  it('is exactly the twelve identifiers of ADR 0021 decision 4', () => {
    expect([...ALLOWED].sort()).toEqual(
      [
        '0BSD',
        'Apache-2.0',
        'BSD-2-Clause',
        'BSD-3-Clause',
        'BlueOak-1.0.0',
        'CC-BY-4.0',
        'CC0-1.0',
        'ISC',
        'MIT',
        'Python-2.0',
        'Unlicense',
        'Zlib',
      ].sort(),
    );
  });

  it('refuses AGPL-3.0 by name, in all three spellings', () => {
    for (const id of ['AGPL-3.0', 'AGPL-3.0-only', 'AGPL-3.0-or-later']) {
      expect(ALLOWED.has(id)).toBe(false);
      expect(NAMED_REFUSALS.get(id)).toMatch(/forbidden \(ADR 0021 decision 4\)/);
    }
  });
});

describe('SPDX expression evaluation', () => {
  it('accepts a bare allowed identifier', () => {
    expect(evaluateExpression('MIT')).toEqual({ ok: true, parsed: true, offenders: [] });
  });

  it('refuses a bare identifier that is not on the list', () => {
    const verdict = evaluateExpression('MPL-2.0');
    expect(verdict.ok).toBe(false);
    expect(verdict.parsed).toBe(true);
    expect(verdict.offenders).toEqual(['MPL-2.0']);
  });

  it('takes the allowed branch of an OR — a dual licence is the licensee\'s choice', () => {
    expect(evaluateExpression('(MIT OR AGPL-3.0)').ok).toBe(true);
    expect(evaluateExpression('MIT OR Apache-2.0').ok).toBe(true);
  });

  it('requires BOTH sides of an AND — one unlisted half taints the package', () => {
    expect(evaluateExpression('(MIT AND Apache-2.0)').ok).toBe(true);
    expect(evaluateExpression('(MIT AND MPL-2.0)').ok).toBe(false);
  });

  it('never allows a WITH exception: the exception modifies the licence', () => {
    const verdict = evaluateExpression('Apache-2.0 WITH LLVM-exception');
    expect(verdict.ok).toBe(false);
    expect(verdict.offenders).toEqual(['Apache-2.0 WITH LLVM-exception']);
  });

  it('does not silently accept the `+` operator as the base identifier', () => {
    expect(evaluateExpression('Apache-2.0+').ok).toBe(false);
  });

  it('reports an unparsable expression as unparsed, not as denied', () => {
    for (const junk of ['', '   ', 'MIT OR', '(MIT', 'MIT )', 'AND MIT', 'MIT ~ ISC']) {
      const verdict = evaluateExpression(junk);
      expect(verdict.ok, junk).toBe(false);
      expect(verdict.parsed, junk).toBe(false);
    }
  });
});

describe('auditLock fails closed', () => {
  it('passes a tree whose every package is allowed', () => {
    const report = auditLock(
      lockWith({
        'node_modules/a': { version: '1.0.0', license: 'MIT' },
        'node_modules/b': { version: '2.0.0', license: '(MIT OR Apache-2.0)' },
      }),
    );
    expect(report.ok).toBe(true);
    expect(report.scanned).toBe(2);
    expect(report.violations).toEqual([]);
    expect(report.rootLicence).toBe('GPL-3.0-or-later');
  });

  // Roadmap W0, definition of done: "A deliberately added AGPL-3.0 package
  // fails the licence gate". This is that test; the exact command-line output
  // of the same case is recorded in the W0 gate report.
  it('refuses a deliberately added AGPL-3.0 package, by name', () => {
    const report = auditLock(
      lockWith({
        'node_modules/audiomotion-analyzer': { version: '4.5.0', license: 'AGPL-3.0-or-later' },
      }),
    );
    expect(report.ok).toBe(false);
    expect(report.violations).toHaveLength(1);
    const [violation] = report.violations;
    expect(violation?.name).toBe('audiomotion-analyzer');
    expect(violation?.version).toBe('4.5.0');
    expect(violation?.reason).toBe('denied');
    expect(violation?.note).toMatch(/AGPL-3\.0 is forbidden/);
  });

  it('refuses a package with NO licence field rather than assuming one', () => {
    const report = auditLock(lockWith({ 'node_modules/mystery': { version: '0.1.0' } }));
    expect(report.ok).toBe(false);
    expect(report.violations[0]?.reason).toBe('absent');
    expect(report.violations[0]?.licence).toBe('<absent>');
  });

  it('refuses a legacy `licenses: [...]` array instead of interpreting it', () => {
    const report = auditLock(
      lockWith({ 'node_modules/ancient': { version: '0.0.1', license: ['MIT'] } }),
    );
    expect(report.ok).toBe(false);
    expect(report.violations[0]?.reason).toBe('malformed');
  });

  it('checks dev and optional platform binaries too — no exemption', () => {
    const report = auditLock(
      lockWith({
        'node_modules/tool': { version: '1.0.0', license: 'MPL-2.0', dev: true },
        'node_modules/tool-linux-x64': { version: '1.0.0', license: 'MPL-2.0', dev: true, optional: true },
      }),
    );
    expect(report.ok).toBe(false);
    expect(report.violations).toHaveLength(2);
  });

  it('skips workspace links — they are this repository, not registry packages', () => {
    const report = auditLock(lockWith({ 'packages/thing': { resolved: 'packages/thing', link: true } }));
    expect(report.ok).toBe(true);
    expect(report.scanned).toBe(0);
    expect(report.skipped).toBe(1);
  });

  it('refuses a file that is not a lockfileVersion 2/3 lock at all', () => {
    const report = auditLock({ name: 'x', lockfileVersion: 1, dependencies: {} });
    expect(report.ok).toBe(false);
    expect(report.violations[0]?.reason).toBe('malformed');
  });

  it('resolves the nested-name form of a lockfile key', () => {
    const report = auditLock(
      lockWith({ 'node_modules/parent/node_modules/child': { version: '1.2.3', license: 'MPL-2.0' } }),
    );
    expect(report.violations[0]?.name).toBe('child');
  });
});

describe('the committed lockfile', () => {
  const lock = JSON.parse(readFileSync(resolve(webRoot, 'package-lock.json'), 'utf8')) as Record<
    string,
    unknown
  >;

  it('audits clean against the allowlist', () => {
    const report = auditLock(lock);
    const offenders = report.violations.map((v) => `${v.name}@${v.version}: ${v.licence}`);
    expect(offenders).toEqual([]);
    expect(report.ok).toBe(true);
  });

  it('scans a non-empty tree — an empty scan is a broken gate, not a clean one', () => {
    expect(auditLock(lock).scanned).toBeGreaterThan(10);
  });

  it('declares the root package GPL-3.0-or-later (ADR 0004 item 2)', () => {
    expect(auditLock(lock).rootLicence).toBe('GPL-3.0-or-later');
  });
});
