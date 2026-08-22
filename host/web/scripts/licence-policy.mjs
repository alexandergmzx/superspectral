// SPDX-FileCopyrightText: 2026 Alexander Gomez
// SPDX-License-Identifier: GPL-3.0-or-later
//
// The npm licence policy of ADR 0021 decision 4, as a pure module.
//
// SPLIT IN TWO ON PURPOSE. This file decides; `check-licences.mjs` reads the
// lockfile, prints and sets the exit status. The decision half therefore has no
// I/O, no `process.exit`, and can be exercised by vitest over hand-built
// lockfiles -- including the AGPL-3.0 negative case roadmap W0 requires, which
// cannot be run against the real lock without actually installing an AGPL
// package.
//
// FAIL-CLOSED IS THE WHOLE POINT (ADR 0021 decision 4: the gate "fails closed
// on an unknown or absent licence"). Every path that cannot prove a package is
// allowed returns a violation:
//   - no `license` field at all            -> `absent`
//   - a field that is not a string         -> `malformed`
//   - an SPDX expression we cannot parse   -> `unparsed`
//   - a parsed expression that is not satisfied by the allowlist -> `denied`
// There is no "assume MIT", no "skip dev dependencies" and no "skip optional
// platform binaries": a dev dependency is code that runs on this machine and on
// the CI runner, and an optional binary is the one that gets installed on the
// platform that has it.
// ----------------------------------------------------------------------------

/**
 * The allowlist, verbatim from ADR 0021 decision 4. Adding a row here is a
 * POLICY change and belongs to Alexander (roadmap W0: "Alexander approves the
 * npm allowlist -- the licence list ... is a policy, not a lockfile, and it is
 * his to sign"). An agent widening this set to make a build pass has defeated
 * the gate; move the dependency instead, or bring the row to him.
 *
 * @type {ReadonlySet<string>}
 */
export const ALLOWED = new Set([
  'MIT',
  'ISC',
  '0BSD',
  'BSD-2-Clause',
  'BSD-3-Clause',
  'Apache-2.0',
  'CC0-1.0',
  'Unlicense',
  'BlueOak-1.0.0',
  'Python-2.0',
  'Zlib',
  'CC-BY-4.0',
]);

/**
 * Identifiers that get a NAMED refusal rather than the generic "not on the
 * allowlist". Being absent from ALLOWED is already fatal, so this map changes
 * no verdict -- it changes the sentence a reader gets, which is what makes the
 * failure actionable at 2 a.m. The AGPL row names ADR 0021's own do-not-use.
 *
 * @type {ReadonlyMap<string, string>}
 */
export const NAMED_REFUSALS = new Map([
  [
    'AGPL-3.0',
    'AGPL-3.0 is forbidden (ADR 0021 decision 4): a served web application is exactly the case its ' +
      'network clause reaches. audioMotion-analyzer is the named do-not-use.',
  ],
  ['AGPL-3.0-only', 'AGPL-3.0 is forbidden (ADR 0021 decision 4) -- see the AGPL-3.0 row.'],
  ['AGPL-3.0-or-later', 'AGPL-3.0 is forbidden (ADR 0021 decision 4) -- see the AGPL-3.0 row.'],
  [
    'GPL-3.0-or-later',
    'A GPL dependency is refused here even though host/ is itself GPL-3.0-or-later: the allowlist ' +
      'exists so a reviewer can check one line, and "GPL is fine because we are GPL" needs a ' +
      'compatibility argument per package (ADR 0021 decision 4).',
  ],
  ['GPL-3.0', 'See the GPL-3.0-or-later row: GPL npm packages are refused by ADR 0021 decision 4.'],
  ['GPL-2.0', 'See the GPL-3.0-or-later row: GPL npm packages are refused by ADR 0021 decision 4.'],
  ['LGPL-2.1', 'LGPL npm packages are refused by ADR 0021 decision 4 (same reason as GPL).'],
  ['LGPL-3.0', 'LGPL npm packages are refused by ADR 0021 decision 4 (same reason as GPL).'],
  [
    'MPL-2.0',
    'MPL-2.0 is not on the ADR 0021 decision 4 allowlist. It reaches this tree through Vite 8, ' +
      "whose `lightningcss` dependency is MPL-2.0; Vite 7 does not pull it in, which is why " +
      'package.json pins `vite: ^7`. Admitting MPL-2.0 is a policy change and is the owner\'s to sign.',
  ],
]);

/**
 * One package that failed the policy.
 *
 * @typedef {object} Violation
 * @property {string} path      Lockfile key, e.g. `node_modules/lightningcss`.
 * @property {string} name      Package name derived from that key.
 * @property {string} version   Resolved version, or `?` when the lock omits it.
 * @property {string} licence   The raw field, or `<absent>` / `<malformed>`.
 * @property {'absent'|'malformed'|'unparsed'|'denied'} reason Why it failed.
 * @property {string} note      One sentence a human can act on.
 */

/** @param {string} key @returns {string} */
function packageNameFromKey(key) {
  const marker = 'node_modules/';
  const index = key.lastIndexOf(marker);
  return index === -1 ? key : key.slice(index + marker.length);
}

/**
 * Tokenise an SPDX licence expression.
 *
 * Deliberately tiny: identifiers, parentheses and the three operators. `+`
 * (`Apache-2.0+`) is part of an identifier, so `Apache-2.0+` is a DIFFERENT
 * token from `Apache-2.0` and is not silently accepted -- fail-closed applies
 * to punctuation too.
 *
 * @param {string} expression
 * @returns {string[] | null} tokens, or null if a character has no meaning here
 */
function tokenise(expression) {
  /** @type {string[]} */
  const tokens = [];
  let index = 0;
  while (index < expression.length) {
    const character = expression[index];
    if (character === ' ' || character === '\t' || character === '\n') {
      index += 1;
      continue;
    }
    if (character === '(' || character === ')') {
      tokens.push(character);
      index += 1;
      continue;
    }
    const match = /^[A-Za-z0-9.+-]+/.exec(expression.slice(index));
    if (match === null) {
      return null;
    }
    tokens.push(match[0]);
    index += match[0].length;
  }
  return tokens;
}

/**
 * Evaluate a tokenised SPDX expression against the allowlist.
 *
 * Grammar (SPDX 2.3, the subset npm metadata actually uses):
 *   or      := and ( 'OR' and )*
 *   and     := primary ( 'AND' primary )*
 *   primary := IDENT [ 'WITH' IDENT ] | '(' or ')'
 *
 * Semantics, both of which are the conservative reading:
 *   OR  -- satisfied when EITHER side is allowed. This is the licensee's choice
 *          and taking the allowed branch is exactly what a dual licence is for.
 *   AND -- satisfied only when BOTH sides are allowed: the package imposes both
 *          sets of terms at once, so one unlisted half taints the whole.
 *   WITH -- an exception modifies the licence, so `X WITH Y` is treated as a
 *          distinct identifier that is not on the allowlist. Never allowed.
 *
 * @param {string} expression
 * @returns {{ok: boolean, parsed: boolean, offenders: string[]}}
 */
export function evaluateExpression(expression) {
  const tokens = tokenise(expression);
  if (tokens === null || tokens.length === 0) {
    return { ok: false, parsed: false, offenders: [] };
  }
  let cursor = 0;
  /** @type {string[]} */
  const offenders = [];
  let failed = false;

  /** @returns {boolean} */
  function parsePrimary() {
    const token = tokens[cursor];
    if (token === undefined) {
      failed = true;
      return false;
    }
    if (token === '(') {
      cursor += 1;
      const inner = parseOr();
      if (tokens[cursor] !== ')') {
        failed = true;
        return false;
      }
      cursor += 1;
      return inner;
    }
    if (token === ')' || token === 'AND' || token === 'OR' || token === 'WITH') {
      failed = true;
      return false;
    }
    cursor += 1;
    if (tokens[cursor] === 'WITH') {
      const exception = tokens[cursor + 1];
      if (exception === undefined) {
        failed = true;
        return false;
      }
      cursor += 2;
      offenders.push(`${token} WITH ${exception}`);
      return false;
    }
    const allowed = ALLOWED.has(token);
    if (!allowed) {
      offenders.push(token);
    }
    return allowed;
  }

  /** @returns {boolean} */
  function parseAnd() {
    let value = parsePrimary();
    while (tokens[cursor] === 'AND') {
      cursor += 1;
      const right = parsePrimary();
      value = value && right;
    }
    return value;
  }

  /** @returns {boolean} */
  function parseOr() {
    let value = parseAnd();
    while (tokens[cursor] === 'OR') {
      cursor += 1;
      const right = parseAnd();
      value = value || right;
    }
    return value;
  }

  const ok = parseOr();
  if (failed || cursor !== tokens.length) {
    return { ok: false, parsed: false, offenders };
  }
  return { ok, parsed: true, offenders };
}

/**
 * Audit a parsed `package-lock.json`.
 *
 * The root entry (key `""`) is skipped: it is this repository's own package,
 * GPL-3.0-or-later by ADR 0004, and the allowlist governs DEPENDENCIES. It is
 * checked separately -- a root that stopped declaring GPL-3.0-or-later would be
 * a licence-boundary break, and is reported as one.
 *
 * `link: true` entries are workspace symlinks into this repository, not
 * registry packages, and are skipped for the same reason as the root.
 *
 * @param {Record<string, unknown>} lock
 * @returns {{ok: boolean, scanned: number, skipped: number, counts: Map<string, number>, violations: Violation[], rootLicence: string|null}}
 */
export function auditLock(lock) {
  const packages = /** @type {Record<string, Record<string, unknown>> | undefined} */ (
    /** @type {any} */ (lock).packages
  );
  /** @type {Violation[]} */
  const violations = [];
  /** @type {Map<string, number>} */
  const counts = new Map();
  let scanned = 0;
  let skipped = 0;

  if (packages === undefined || typeof packages !== 'object') {
    violations.push({
      path: 'package-lock.json',
      name: 'package-lock.json',
      version: '?',
      licence: '<absent>',
      reason: 'malformed',
      note:
        'No `packages` map: this is not a lockfileVersion 2 or 3 file. `npm ci` would not accept ' +
        'it either; regenerate with `npm install --package-lock-only --ignore-scripts`.',
    });
    return { ok: false, scanned: 0, skipped: 0, counts, violations, rootLicence: null };
  }

  const rootEntry = packages[''];
  const rootLicence = typeof rootEntry?.['license'] === 'string' ? String(rootEntry['license']) : null;

  for (const [key, entry] of Object.entries(packages)) {
    if (key === '') {
      continue;
    }
    if (entry?.['link'] === true) {
      skipped += 1;
      continue;
    }
    scanned += 1;
    const version = typeof entry?.['version'] === 'string' ? String(entry['version']) : '?';
    const name = packageNameFromKey(key);
    const raw = entry?.['license'];

    if (raw === undefined || raw === null) {
      violations.push({
        path: key,
        name,
        version,
        licence: '<absent>',
        reason: 'absent',
        note:
          'The lockfile states no licence for this package. Fail-closed (ADR 0021 decision 4): an ' +
          'absent licence is refused, never assumed. Read the package\'s own LICENSE at this exact ' +
          'version before proposing anything.',
      });
      continue;
    }
    if (typeof raw !== 'string') {
      violations.push({
        path: key,
        name,
        version,
        licence: '<malformed>',
        reason: 'malformed',
        note:
          'The `license` field is not a string (npm\'s legacy `licenses: [...]` array, or worse). ' +
          'Refused rather than interpreted.',
      });
      continue;
    }

    counts.set(raw, (counts.get(raw) ?? 0) + 1);
    const verdict = evaluateExpression(raw);
    if (verdict.ok) {
      continue;
    }
    const named = verdict.offenders.map((id) => NAMED_REFUSALS.get(id)).find((note) => note !== undefined);
    violations.push({
      path: key,
      name,
      version,
      licence: raw,
      reason: verdict.parsed ? 'denied' : 'unparsed',
      note:
        named ??
        (verdict.parsed
          ? `Not on the ADR 0021 decision 4 allowlist: ${verdict.offenders.join(', ') || raw}.`
          : `Could not be parsed as an SPDX expression, so it cannot be shown to be allowed: ${raw}.`),
    });
  }

  return { ok: violations.length === 0, scanned, skipped, counts, violations, rootLicence };
}
