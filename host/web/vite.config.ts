// SPDX-FileCopyrightText: 2026 Alexander Gomez
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Vite build/dev configuration for the host web application (ADR 0021 decision 1).
// Every non-obvious option states WHY, the way this repository comments .envrc:
// a config that cannot be read as an argument is a config nobody dares change.
// ----------------------------------------------------------------------------

import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

const here = dirname(fileURLToPath(import.meta.url));

// mkcert output, if the owner has minted it. Kept INSIDE host/web/certs/ only
// because that path is gitignored (root .gitignore also ignores *.pem / *.key);
// host/README.md's mkcert recipe puts the pair outside the repository and passes
// it to uvicorn instead. Both are machine-local secrets and neither is shareable.
const certFile = resolve(here, 'certs/cert.pem');
const keyFile = resolve(here, 'certs/key.pem');

// HTTPS is enabled ONLY when BOTH halves exist. Rationale (ADR 0021 decision 8):
// navigator.mediaDevices is undefined on an insecure origin that is not
// localhost, so phone-on-LAN needs TLS -- but localhost IS a secure context, so
// forcing TLS on the laptop would buy nothing and cost a trust-store dance. An
// absent certificate therefore degrades to plain HTTP rather than failing: the
// dev server must start for a contributor who has never run mkcert.
const httpsPair =
  existsSync(certFile) && existsSync(keyFile)
    ? { cert: readFileSync(certFile), key: readFileSync(keyFile) }
    : undefined;

export default defineConfig({
  // W1 runs the transform in a Worker and the capture in an AudioWorklet.
  // AudioWorklet modules are ES modules by specification -- `format: 'iife'`
  // (Vite's default for workers) cannot be registered by addModule(), so this
  // line has to be here before the first worker file exists, not after.
  worker: { format: 'es' },

  build: {
    // Match tsconfig's target. Chosen for top-level await and the ES2022 class
    // fields the DSP module will use; every browser this application supports
    // (Chromium/Firefox current, the owner's phone) is well past it.
    target: 'es2022',
    // Sourcemaps in production builds on purpose: the deployment is a laptop on
    // a LAN, not a public site, and a spectrum that is 0.02 dB off the oracle is
    // debugged in the browser that produced it.
    sourcemap: true,
  },

  server: {
    // Bind every interface. Phone-on-LAN is a REQUIREMENT (ADR 0021 decision 8,
    // owner 2026-08-22), so the default localhost-only bind is wrong here.
    host: true,

    // The front end never ships its own copy of a preset (ADR 0021 decision 7a):
    // it fetches /api/presets. In `npm run dev` the front end is on Vite's port
    // and the FastAPI backend on 8000, so same-origin fetches need this proxy.
    // In a built deployment there is no proxy at all -- uvicorn mounts dist/ and
    // serves both halves from one origin, which is also why the client uses
    // relative URLs and never an absolute backend address.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },

    // Spread rather than `https: httpsPair`: tsconfig sets
    // exactOptionalPropertyTypes, under which an explicit `undefined` is not the
    // same as an absent key.
    ...(httpsPair ? { https: httpsPair } : {}),
  },
});
