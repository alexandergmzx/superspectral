// SPDX-FileCopyrightText: 2026 Alexander Gomez
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Bootstrap for the host web application (ADR 0021, roadmap W0).
//
// W0 ships exactly one behaviour, deliberately: prove the two contracts the
// rest of track W stands on.
//
//   1. Secure context. navigator.mediaDevices is undefined on an insecure
//      origin that is not localhost (ADR 0021 decision 8). Detected here and
//      shown, so that the phone-on-LAN failure is a sentence on screen instead
//      of a TypeError in a console nobody has open on a phone.
//   2. The preset contract. The six presets are fetched from the backend and
//      rendered with their sha256 (ADR 0021 decision 7a). The front end never
//      ships its own copy and the bundler never embeds one; this list is the
//      visible end-to-end proof that byte-identity holds.
//
// No audio, no canvas drawing: that is W1.
// ----------------------------------------------------------------------------

import { ApiError, api, type PresetSummary } from './api/client';

/** Look an element up or fail at boot — a missing id is a bug in index.html. */
function required<T extends Element>(id: string): T {
  const element = document.getElementById(id);
  if (element === null) {
    throw new Error(`index.html is missing #${id}`);
  }
  return element as unknown as T;
}

interface SecureContextVerdict {
  readonly usable: boolean;
  readonly reason: string;
}

/**
 * Why capture is or is not possible here.
 *
 * Both halves are checked, not just one: `isSecureContext` can be true while
 * `navigator.mediaDevices` is still absent (a browser without the API, or a
 * permissions policy that removed it), and reporting "insecure origin" in that
 * case would send the owner off minting a certificate that changes nothing.
 */
export function inspectSecureContext(view: Window = window): SecureContextVerdict {
  const secure = view.isSecureContext;
  const media = view.navigator.mediaDevices !== undefined;
  if (secure && media) {
    return { usable: true, reason: `secure context on ${view.location.origin}` };
  }
  if (!secure) {
    return {
      usable: false,
      reason:
        `${view.location.origin} is not a secure context, so navigator.mediaDevices is unavailable. ` +
        'localhost is exempt; a LAN address is not — serve the app over HTTPS with an mkcert ' +
        'certificate (host/README.md, ADR 0021 decision 8).',
    };
  }
  return {
    usable: false,
    reason:
      'This origin is a secure context but navigator.mediaDevices is absent — the browser does ' +
      'not expose the capture API here (an old browser, or a permissions policy that removed it).',
  };
}

function applySecureContextVerdict(verdict: SecureContextVerdict): void {
  const banner = required<HTMLElement>('insecure-banner');
  const detail = required<HTMLElement>('insecure-banner-detail');
  const button = required<HTMLButtonElement>('capture-button');
  const state = required<HTMLElement>('capture-state');

  if (verdict.usable) {
    banner.hidden = true;
    state.textContent = `idle — ${verdict.reason}; W1 opens the stream`;
    // Still disabled: W0 has nothing to start. The button is enabled by W1,
    // which is also where the getUserMedia constraints land.
    button.disabled = true;
    return;
  }

  detail.textContent = verdict.reason;
  banner.hidden = false;
  button.disabled = true;
  state.textContent = 'capture unavailable — insecure origin';
}

function presetItem(preset: PresetSummary): HTMLLIElement {
  const item = document.createElement('li');
  item.className = 'preset';

  const name = document.createElement('span');
  name.className = 'preset__name';
  name.textContent = preset.name;

  const targets = document.createElement('span');
  targets.className = 'preset__targets';
  targets.textContent = preset.targets.join(' · ');

  // The digest is the point of this list, so it is rendered in full rather than
  // truncated: a truncated hash is a hash nobody can compare against
  // `sha256sum protocols/presets/<id>.json`.
  const digest = document.createElement('code');
  digest.className = 'preset__sha';
  digest.textContent = preset.sha256;
  digest.title = `sha256 of ${String(preset.bytes)} bytes served at ${preset.url}`;

  item.append(name, targets, digest);
  return item;
}

async function renderPresets(): Promise<void> {
  const list = required<HTMLUListElement>('preset-list');
  try {
    const presets = await api.getPresets();
    list.replaceChildren(...presets.map(presetItem));
    if (presets.length !== 6) {
      // Not a hard failure in the browser — the backend's own test owns the
      // count — but a visible one, because six is the number ADR 0021 names.
      const note = document.createElement('li');
      note.className = 'muted';
      note.textContent = `${String(presets.length)} presets served; ADR 0021 expects six.`;
      list.append(note);
    }
  } catch (error) {
    list.replaceChildren(errorItem('presets unavailable', error));
  }
}

function errorItem(what: string, error: unknown): HTMLLIElement {
  const item = document.createElement('li');
  item.className = 'error';
  const detail =
    error instanceof ApiError
      ? `${what}: ${error.code} — ${error.message} (HTTP ${String(error.status)})`
      : `${what}: ${error instanceof Error ? error.message : String(error)}`;
  item.textContent = detail;
  return item;
}

async function renderVersion(): Promise<void> {
  const target = required<HTMLElement>('backend-version');
  try {
    const version = await api.getVersion();
    const api_ = version.api === undefined ? '' : ` · api ${version.api}`;
    target.textContent = `backend: ${version.version}${api_}`;
  } catch (error) {
    target.textContent =
      error instanceof ApiError
        ? `backend unreachable: ${error.code} (HTTP ${String(error.status)})`
        : `backend unreachable: ${error instanceof Error ? error.message : String(error)}`;
    target.classList.add('error');
  }
}

function main(): void {
  applySecureContextVerdict(inspectSecureContext());
  // Deliberately not awaited together with a failure that aborts the other:
  // a dead /api/version must not blank the preset list, and vice versa.
  void renderVersion();
  void renderPresets();
}

main();
