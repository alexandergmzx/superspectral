// SPDX-FileCopyrightText: 2026 Alexander Gomez
// SPDX-License-Identifier: GPL-3.0-or-later
//
// The typed boundary to the FastAPI backend (ADR 0021 decision 1).
//
// THIS IS THE ONLY FILE THAT KNOWS THE BACKEND'S ROUTES. Everything else asks
// for presets or a version; nothing else spells `/api/...`. When the backend
// moves a path, exactly one file changes and `tsc --noEmit` finds every caller.
//
// URLs are RELATIVE on purpose: in `npm run dev` Vite proxies /api to
// 127.0.0.1:8000 (vite.config.ts), and in a built deployment uvicorn mounts
// dist/ and serves both halves from one origin. An absolute backend address
// would break phone-on-LAN, where the origin is the laptop's LAN address.
// ----------------------------------------------------------------------------

/** One row of `GET /api/presets` — the summary, not the preset itself. */
export interface PresetSummary {
  /** Preset id; also the file stem under `protocols/presets/`. */
  readonly id: string;
  /** sha256 of the canonical file's BYTES (ADR 0021 decision 7a). */
  readonly sha256: string;
  /** Human-readable name, from the preset's own `name` field (ADR 0010). */
  readonly name: string;
  /** `["watch","host"]` or `["host"]` — "host" covers CLI and web app alike. */
  readonly targets: readonly string[];
  /** Size of the canonical file in bytes; the digest's subject. */
  readonly bytes: number;
  /** Where the byte-identical file itself lives, e.g. `/api/presets/live_singing`. */
  readonly url: string;
}

/**
 * `GET /api/version`.
 *
 * The exact field set is `(prov.)` — the backend (W0-BE) owns the payload and
 * this decoder was written before it existed. `version` is the one field this
 * client requires; everything else the backend sends is preserved verbatim in
 * `raw` so a field added there does not need a change here to become visible.
 * When /api/version is frozen, promote its fields out of `raw` and drop this note.
 */
export interface Version {
  /** Version of the serving backend. */
  readonly version: string;
  /** Contract version of `/api` itself, when the backend distinguishes them. */
  readonly api?: string;
  /** Every field the backend sent, decoded but not interpreted. */
  readonly raw: Readonly<Record<string, unknown>>;
}

/** The backend's error envelope: `{"error": {"code": ..., "message": ..., ...}}`. */
export interface ApiErrorBody {
  readonly code: string;
  readonly message: string;
  readonly details?: Readonly<Record<string, unknown>>;
}

/**
 * A decoded backend failure. Carries the HTTP status AND the backend's own
 * code, because the two answer different questions: 404 says "no such route or
 * id", `code` says which loader rule refused (V0 on a tampered preset, for
 * instance — roadmap W0's definition of done requires that to fail loudly
 * rather than be served).
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Readonly<Record<string, unknown>>;

  constructor(status: number, code: string, message: string, details: Readonly<Record<string, unknown>> = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

/**
 * The CSRF marker the backend requires on non-GET requests.
 *
 * A custom request header cannot be set by a cross-origin form or image, so its
 * presence proves the request came from this application's own script and not
 * from a page the singer happened to have open. Cheap, no token round trip, and
 * the backend rejects a write without it.
 */
export const REQUESTED_WITH_HEADER = 'X-Requested-With';
export const REQUESTED_WITH_VALUE = 'spectral-web';

/** A method that changes state on the backend and therefore carries the marker. */
function isWrite(method: string): boolean {
  return method.toUpperCase() !== 'GET';
}

export interface ApiClientOptions {
  /** Prefix for every route. Relative by default; see the note at the top. */
  readonly baseUrl?: string;
  /** Injected for tests; defaults to the platform `fetch`. */
  readonly fetch?: typeof globalThis.fetch;
}

export interface ApiClient {
  readonly getPresets: () => Promise<readonly PresetSummary[]>;
  /** The canonical preset file, as TEXT — the bytes, not a re-serialised object. */
  readonly getPresetSource: (id: string) => Promise<string>;
  readonly getVersion: () => Promise<Version>;
  /** Escape hatch for W2+ writes (uploads, injection runs). Sends the marker. */
  readonly request: <T>(path: string, init?: RequestInit) => Promise<T>;
}

function asRecord(value: unknown): Readonly<Record<string, unknown>> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asString(value: unknown, fallback: string): string {
  return typeof value === 'string' ? value : fallback;
}

/**
 * Turn a non-2xx response into a typed ApiError.
 *
 * Never throws on its own: a backend that died mid-handler can return HTML, an
 * empty body or a proxy's error page, and losing the status behind a JSON parse
 * error would be the second failure hiding the first.
 */
async function decodeError(response: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  const envelope = asRecord(body);
  const error = envelope ? asRecord(envelope['error']) : null;
  if (error) {
    const details = asRecord(error['details']);
    return new ApiError(
      response.status,
      asString(error['code'], 'unknown'),
      asString(error['message'], `HTTP ${String(response.status)}`),
      details ?? {},
    );
  }
  // Not our envelope: keep the status and say so rather than inventing a code.
  return new ApiError(
    response.status,
    'non_envelope_response',
    `HTTP ${String(response.status)} ${response.statusText}`.trim(),
  );
}

export function createApiClient(options: ApiClientOptions = {}): ApiClient {
  const baseUrl = options.baseUrl ?? '/api';
  const injected = options.fetch;

  async function raw(path: string, init: RequestInit = {}): Promise<Response> {
    // Resolved per call, not at construction: the module-level `api` below is
    // built at import time, and a global `fetch` read then would be captured
    // before a test (or a Worker bootstrap) had a chance to install its own.
    // Bound because an unbound globalThis.fetch is an Illegal invocation.
    const doFetch = injected ?? globalThis.fetch.bind(globalThis);
    const method = init.method ?? 'GET';
    const headers = new Headers(init.headers);
    headers.set('Accept', 'application/json');
    if (isWrite(method)) {
      headers.set(REQUESTED_WITH_HEADER, REQUESTED_WITH_VALUE);
    }
    const response = await doFetch(`${baseUrl}${path}`, { ...init, method, headers });
    if (!response.ok) {
      throw await decodeError(response);
    }
    return response;
  }

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await raw(path, init);
    return (await response.json()) as T;
  }

  return {
    request,

    async getPresets(): Promise<readonly PresetSummary[]> {
      const body = await request<unknown>('/presets');
      // The backend may answer with a bare array or with {presets: [...]}; both
      // are accepted rather than guessed at, and anything else is a typed error
      // instead of an `undefined.map` three frames later.
      const list = Array.isArray(body) ? body : asRecord(body)?.['presets'];
      if (!Array.isArray(list)) {
        throw new ApiError(200, 'malformed_presets', 'GET /api/presets did not return a list of presets');
      }
      return list as readonly PresetSummary[];
    },

    async getPresetSource(id: string): Promise<string> {
      // TEXT, not .json(): the point of this route is the BYTES the watch and
      // the host both hash (ADR 0021 decision 7a). Parsing and re-serialising
      // would destroy the very property being displayed.
      const response = await raw(`/presets/${encodeURIComponent(id)}`);
      return await response.text();
    },

    async getVersion(): Promise<Version> {
      const body = await request<unknown>('/version');
      const record = asRecord(body) ?? {};
      const api = record['api'];
      return {
        version: asString(record['version'], 'unknown'),
        ...(typeof api === 'string' ? { api } : {}),
        raw: record,
      };
    },
  };
}

/** The process-wide client used by the application; tests build their own. */
export const api: ApiClient = createApiClient();
