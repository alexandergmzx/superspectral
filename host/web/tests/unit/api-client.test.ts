// SPDX-FileCopyrightText: 2026 Alexander Gomez
// SPDX-License-Identifier: GPL-3.0-or-later
//
// The typed backend boundary's tests (src/api/client.ts, ADR 0021 decision 1).
//
// `fetch` is INJECTED rather than stubbed on globalThis: the client resolves it
// per call precisely so a test can supply its own, and injecting keeps the two
// suites in this file independent of each other's ordering.
//
// What is being pinned here is the CONTRACT, not the implementation:
//   * relative URLs (phone-on-LAN breaks the moment an absolute host appears);
//   * the preset route returns TEXT, never a re-serialised object — byte
//     identity is the whole point of ADR 0021 decision 7(a);
//   * the CSRF marker rides on writes and only on writes;
//   * a backend failure arrives as a typed ApiError carrying BOTH the HTTP
//     status and the backend's own code (V0 on a tampered preset, for example).
// ----------------------------------------------------------------------------

import { describe, expect, it } from 'vitest';

import {
  ApiError,
  REQUESTED_WITH_HEADER,
  REQUESTED_WITH_VALUE,
  createApiClient,
} from '../../src/api/client';

interface Call {
  readonly url: string;
  readonly method: string;
  readonly headers: Headers;
}

/** A fetch double that records what it was asked and replays a scripted answer. */
function recorder(respond: (url: string) => Response): {
  fetch: typeof globalThis.fetch;
  calls: Call[];
} {
  const calls: Call[] = [];
  const fetchDouble = ((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({
      url,
      method: init?.method ?? 'GET',
      headers: new Headers(init?.headers),
    });
    return Promise.resolve(respond(url));
  }) as typeof globalThis.fetch;
  return { fetch: fetchDouble, calls };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('routing', () => {
  it('prefixes every route with a RELATIVE /api by default', async () => {
    const { fetch, calls } = recorder(() => json([]));
    await createApiClient({ fetch }).getPresets();
    expect(calls[0]?.url).toBe('/api/presets');
  });

  it('honours an explicit baseUrl', async () => {
    const { fetch, calls } = recorder(() => json({ version: '0.1.0' }));
    await createApiClient({ fetch, baseUrl: '/backend' }).getVersion();
    expect(calls[0]?.url).toBe('/backend/version');
  });

  it('percent-encodes a preset id rather than pasting it into the path', async () => {
    const { fetch, calls } = recorder(() => new Response('{}', { status: 200 }));
    await createApiClient({ fetch }).getPresetSource('../etc/passwd');
    expect(calls[0]?.url).toBe('/api/presets/..%2Fetc%2Fpasswd');
  });
});

describe('the CSRF marker', () => {
  it('is absent on a GET', async () => {
    const { fetch, calls } = recorder(() => json([]));
    await createApiClient({ fetch }).getPresets();
    expect(calls[0]?.headers.has(REQUESTED_WITH_HEADER)).toBe(false);
  });

  it('rides on every non-GET method', async () => {
    for (const method of ['POST', 'PUT', 'PATCH', 'DELETE']) {
      const { fetch, calls } = recorder(() => json({ ok: true }));
      await createApiClient({ fetch }).request('/uploads', { method });
      expect(calls[0]?.headers.get(REQUESTED_WITH_HEADER), method).toBe(REQUESTED_WITH_VALUE);
    }
  });
});

describe('GET /api/presets', () => {
  const summary = {
    id: 'live_singing',
    sha256: 'a'.repeat(64),
    name: 'Live singing',
    targets: ['watch', 'host'],
    bytes: 1234,
    url: '/api/presets/live_singing',
  };

  it('accepts a bare array', async () => {
    const { fetch } = recorder(() => json([summary]));
    await expect(createApiClient({ fetch }).getPresets()).resolves.toEqual([summary]);
  });

  it('accepts the {presets: [...]} envelope', async () => {
    const { fetch } = recorder(() => json({ presets: [summary] }));
    await expect(createApiClient({ fetch }).getPresets()).resolves.toEqual([summary]);
  });

  it('raises a typed error instead of an undefined.map three frames later', async () => {
    const { fetch } = recorder(() => json({ nope: true }));
    await expect(createApiClient({ fetch }).getPresets()).rejects.toMatchObject({
      name: 'ApiError',
      code: 'malformed_presets',
    });
  });
});

describe('GET /api/presets/{id}', () => {
  it('returns the BYTES as text — no parse, no re-serialisation', async () => {
    // Deliberately not canonical JSON: trailing newline, two-space indent, key
    // order. A client that parsed and re-serialised would return none of it,
    // and the sha256 displayed beside the name would be a different file's.
    const canonical = '{\n  "schema_version": 1,\n  "id": "live_singing"\n}\n';
    const { fetch } = recorder(() => new Response(canonical, { status: 200 }));
    await expect(createApiClient({ fetch }).getPresetSource('live_singing')).resolves.toBe(canonical);
  });
});

describe('error decoding', () => {
  it('carries the backend code and details beside the HTTP status', async () => {
    const { fetch } = recorder(() =>
      json(
        {
          error: {
            code: 'preset_invalid',
            message: 'V0: sha256 mismatch',
            details: { rule: 'V0', id: 'live_singing' },
          },
        },
        409,
      ),
    );
    const error = await createApiClient({ fetch })
      .getPresets()
      .catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    const api = error as ApiError;
    expect(api.status).toBe(409);
    expect(api.code).toBe('preset_invalid');
    expect(api.message).toBe('V0: sha256 mismatch');
    expect(api.details).toEqual({ rule: 'V0', id: 'live_singing' });
  });

  it('keeps the status when the body is not our envelope', async () => {
    const { fetch } = recorder(
      () => new Response('<html>502 Bad Gateway</html>', { status: 502, statusText: 'Bad Gateway' }),
    );
    const error = (await createApiClient({ fetch })
      .getVersion()
      .catch((caught: unknown) => caught)) as ApiError;
    expect(error.status).toBe(502);
    expect(error.code).toBe('non_envelope_response');
  });

  it('does not let a JSON parse failure hide the HTTP status', async () => {
    const { fetch } = recorder(
      () => new Response('', { status: 500, headers: { 'Content-Type': 'application/json' } }),
    );
    const error = (await createApiClient({ fetch })
      .getPresets()
      .catch((caught: unknown) => caught)) as ApiError;
    expect(error.status).toBe(500);
  });
});

describe('GET /api/version', () => {
  it('preserves every field the backend sent in `raw`', async () => {
    const { fetch } = recorder(() => json({ version: '0.1.0', api: '1', git: 'deadbeef' }));
    const version = await createApiClient({ fetch }).getVersion();
    expect(version.version).toBe('0.1.0');
    expect(version.api).toBe('1');
    expect(version.raw['git']).toBe('deadbeef');
  });

  it('reports an absent version as "unknown" rather than undefined', async () => {
    const { fetch } = recorder(() => json({}));
    const version = await createApiClient({ fetch }).getVersion();
    expect(version.version).toBe('unknown');
    expect(version.api).toBeUndefined();
  });
});
