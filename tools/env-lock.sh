#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
#
# env-lock.sh — regenerate the machine-readable block of docs/devenv/env.lock.md.
#
# The only side effect is rewriting the text between the two marker lines
#   <!-- env-lock:begin -->  and  <!-- env-lock:end -->
# in docs/devenv/env.lock.md. Everything outside the markers is hand-written and
# left untouched. With --check the file is not modified; the script exits 1 if
# the MACHINE-INVARIANT rows of the regenerated block differ from what is
# committed (CI runs this inside the digest-pinned container). Invariant rows:
# IDF tag, IDF commit SHA, submodule sync count, esptool / esp-coredump /
# idf-component-manager / esp-idf-kconfig / esp-idf-size versions, the CI
# container digest and the dependencies.lock sha256. Host-specific rows (paths,
# distro, kernel, glibc, cmake/ninja/ccache, uv, udev symlink, leaked env vars,
# the generation date) are informational and are NOT compared — they legitimately
# differ between the developer's machine and the container.
#
# Run from an activated ESP-IDF shell (cd into the repo; direnv sources .envrc).
# Rationale: critic B4 — ".envrc pins the IDF *path*, not its *contents*"; this
# file pins the contents. Roadmap phase E1 fills it for the first time.
set -euo pipefail

usage() {
  cat <<USAGE
usage: tools/env-lock.sh [--check] [--output FILE]
  --check        do not write; exit 1 if the machine-invariant rows of the
                 generated block differ from FILE (see the header comment)
  --output FILE  target markdown file (default: docs/devenv/env.lock.md)
USAGE
}

# Rows compared by --check (regex over the rendered table's first column).
# shellcheck disable=SC2016  # single quotes are deliberate: this is an ERE, not a template.
INVARIANT_ROWS='^\| (ESP-IDF tag|ESP-IDF commit SHA|ESP-IDF submodules out of sync|esptool|esp-coredump|idf-component-manager|esp-idf-kconfig|esp-idf-size|CI container \(digest-pinned\)|`dependencies\.lock` sha256) \|'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$REPO_ROOT/docs/devenv/env.lock.md"
CHECK=0
while [ $# -gt 0 ]; do
  case "$1" in
    --check) CHECK=1 ;;
    --output) OUT="$2"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

BEGIN='<!-- env-lock:begin -->'
END='<!-- env-lock:end -->'
[ -f "$OUT" ] || { echo "error: $OUT does not exist" >&2; exit 2; }
# shellcheck disable=SC2015  # A && B || C is intended here and is correct: C runs iff either
# grep fails, which is exactly the condition. There is no "A true, B false" case to mishandle.
grep -qF "$BEGIN" "$OUT" && grep -qF "$END" "$OUT" || {
  echo "error: $OUT lacks the $BEGIN / $END markers" >&2; exit 2; }

# --- helpers -----------------------------------------------------------------
have() { command -v "$1" >/dev/null 2>&1; }
dirnames() { # dirnames <glob...> -> space-separated basenames, or empty if the glob did not match.
  # A glob loop rather than `ls | xargs basename`: ls output is not safely parseable for names
  # with spaces or newlines (SC2011), and an unmatched glob must yield nothing, not itself.
  local out="" d
  for d in "$@"; do [ -d "$d" ] || continue; out="$out$(basename "$d") "; done
  printf '%s' "$out"
}
ver() { # ver <cmd> <args...> -> first line of output or "not found"
  local c="$1"; shift
  # (awk, not head: head closes the pipe early and SIGPIPEs the producer under pipefail)
  if have "$c"; then "$c" "$@" 2>&1 | awk 'NR==1'; else echo "not found"; fi
}
pyver() { # pyver <distribution> -> installed version inside the IDF venv, or "not installed"
  "$PY" - "$1" <<'PYEOF' 2>/dev/null || echo "not installed"
import sys, importlib.metadata as m
try:
    print(m.version(sys.argv[1]))
except m.PackageNotFoundError:
    print("not installed")
PYEOF
}

# --- gather ------------------------------------------------------------------
TODAY="$(date -u +%Y-%m-%d)"
IDF_PATH="${IDF_PATH:-}"
IDF_TOOLS_PATH="${IDF_TOOLS_PATH:-}"
if [ -z "$IDF_PATH" ] || [ ! -d "$IDF_PATH" ]; then
  echo "error: IDF_PATH is unset or missing — run inside the direnv-activated repo shell" >&2
  exit 2
fi
PY="${IDF_PYTHON_ENV_PATH:+$IDF_PYTHON_ENV_PATH/bin/python}"
PY="${PY:-$(command -v python3)}"

IDF_TAG="$(git -C "$IDF_PATH" describe --tags --exact-match 2>/dev/null || git -C "$IDF_PATH" describe --tags --always --dirty)"
IDF_SHA="$(git -C "$IDF_PATH" rev-parse HEAD)"
IDF_SUBMODULES_DIRTY="$(git -C "$IDF_PATH" submodule status --recursive 2>/dev/null | grep -c '^[+-U]' || true)"
IDF_PY_VERSION="$(ver idf.py --version)"
PY_PATH="$("$PY" -c 'import sys; print(sys.executable)')"
PY_VERSION="$("$PY" -c 'import sys; print(sys.version.split()[0])')"
PY_HOME="$(grep -E '^home *=' "${IDF_PYTHON_ENV_PATH:-/nonexistent}/pyvenv.cfg" 2>/dev/null | sed 's/^home *= *//' || true)"
DISTRO="$(. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME:-unknown} (ID_LIKE=${ID_LIKE:-?})")"
KERNEL="$(uname -sr)"
GLIBC="$(getconf GNU_LIBC_VERSION 2>/dev/null || echo unknown)"
CMAKE="$(ver cmake --version) [$(command -v cmake 2>/dev/null || echo -)]"
NINJA="$(ver ninja --version) [$(command -v ninja 2>/dev/null || echo -)]"
CCACHE="$(ver ccache --version) [$(command -v ccache 2>/dev/null || echo -)]"
GIT="$(ver git --version)"
DIRENV="$(ver direnv version)"
# uv is not an IDF tool: it owns the three repo-side Python projects (host/ and
# python-scripts/{synth_signals,golden_compare}; setup.md section 10). Recorded
# because CI pins the same version (`pip install uv==0.11.32` in ci.yml) and the
# three uv.lock files are only reproducible by the resolver that wrote them.
# Informational row: not in INVARIANT_ROWS, the container does not carry uv.
UV="$(ver uv --version) [$(command -v uv 2>/dev/null || echo -)]"
# Node and npm are the FOURTH environment on this machine (setup.md section 11),
# added 2026-08-22 with the host web application (ADR 0021, roadmap W0). Not IDF
# tools, never mixed with the three Python environments, and never installed by
# install.sh -- recorded here because host/web/.nvmrc pins the version the CI
# `web` job feeds to actions/setup-node, so a drift between this machine and the
# runner shows up in the inventory before it shows up in a red build.
# Informational rows: not in INVARIANT_ROWS, the IDF container carries no Node.
NODE="$(ver node --version) [$(command -v node 2>/dev/null || echo -)]"
NPM="$(ver npm --version) [$(command -v npm 2>/dev/null || echo -)]"
OPENOCD="$(ver openocd --version)"
XTENSA_GCC="$(ver xtensa-esp32s3-elf-gcc --version)"
CLANGD="$(dirnames "$IDF_TOOLS_PATH"/tools/esp-clang/*/)"
ESPTOOL="$(pyver esptool)"
ESPCOREDUMP="$(pyver esp-coredump)"
CM="$(pyver idf-component-manager)"
KCONFIG="$(pyver esp-idf-kconfig)"
IDFSIZE="$(pyver esp-idf-size)"
PYTEST_EMBEDDED="$(pyver pytest-embedded)"
IDF_BUILD_APPS="$(pyver idf-build-apps)"
SBOM="$(pyver esp-idf-sbom)"
QEMU_INSTALLED="$(dirnames "$IDF_TOOLS_PATH"/tools/qemu-xtensa/*/)"
CONTAINER="$(grep -rhoE 'espressif/idf:v[0-9.]+@sha256:[0-9a-f]{64}' "$REPO_ROOT/.github/workflows" 2>/dev/null | sort -u | awk 'NR==1' || true)"
LOCK="$REPO_ROOT/firmware/twatch-s3/dependencies.lock"
LOCK_SHA="$( [ -f "$LOCK" ] && sha256sum "$LOCK" | cut -c1-64 || echo 'dependencies.lock not yet generated (phase E1)')"
UDEV_SYMLINK="$( [ -L /dev/ttyTWATCH ] && readlink -f /dev/ttyTWATCH || echo 'absent (watch not connected, or udev rule not installed)')"
LEAK="$(env | grep -oE '^(IDF_COMPONENT_LOCAL_STORAGE_URL|PYTHONPATH|CMAKE_PREFIX_PATH|LD_LIBRARY_PATH|AMENT_PREFIX_PATH)=' | tr -d '=' | paste -sd, - || true)"
LEAK="${LEAK:-none}"

TOOLS_CHECK="$("$PY" "$IDF_PATH/tools/idf_tools.py" --idf-path "$IDF_PATH" check 2>&1 || true)"
TOOLS_LIST="$("$PY" "$IDF_PATH/tools/idf_tools.py" --idf-path "$IDF_PATH" list 2>&1 | grep -E '^\*|recommended' || true)"

# --- render ------------------------------------------------------------------
BLOCK="$(cat <<BLK
$BEGIN
_Generated by \`tools/env-lock.sh\` on $TODAY. Do not edit inside the markers._

| Field | Value |
|---|---|
| ESP-IDF tag | \`$IDF_TAG\` |
| ESP-IDF commit SHA | \`$IDF_SHA\` |
| ESP-IDF submodules out of sync | $IDF_SUBMODULES_DIRTY (must be 0) |
| \`idf.py --version\` | \`$IDF_PY_VERSION\` |
| \`IDF_PATH\` | \`$IDF_PATH\` |
| \`IDF_TOOLS_PATH\` | \`$IDF_TOOLS_PATH\` |
| Python (venv interpreter) | \`$PY_PATH\` — $PY_VERSION |
| Python base (\`pyvenv.cfg home\`) | \`${PY_HOME:-unknown}\` (must be \`/usr/bin\`, pitfall A6) |
| Host distro | $DISTRO |
| Kernel | $KERNEL |
| glibc | $GLIBC (QEMU needs >= 2.31) |
| cmake | $CMAKE |
| ninja | $NINJA |
| ccache | $CCACHE |
| git | $GIT |
| direnv | $DIRENV |
| uv (repo Python projects, not IDF) | $UV |
| node (host web application, not IDF) | $NODE |
| npm (host web application, not IDF) | $NPM |
| xtensa-esp32s3-elf-gcc | $XTENSA_GCC |
| esp-clang (installed dirs) | ${CLANGD:-none} |
| openocd-esp32 | $OPENOCD |
| qemu-xtensa (installed dirs) | ${QEMU_INSTALLED:-none} |
| esptool | $ESPTOOL |
| esp-coredump | $ESPCOREDUMP |
| idf-component-manager | $CM |
| esp-idf-kconfig | $KCONFIG |
| esp-idf-size | $IDFSIZE |
| idf-build-apps | $IDF_BUILD_APPS |
| pytest-embedded | $PYTEST_EMBEDDED |
| esp-idf-sbom | $SBOM |
| CI container (digest-pinned) | ${CONTAINER:-TBD — not yet referenced in .github/workflows} |
| \`dependencies.lock\` sha256 | \`$LOCK_SHA\` |
| \`/dev/ttyTWATCH\` | $UDEV_SYMLINK |
| Leaked env vars (must be none) | \`$LEAK\` |

\`idf_tools.py check\` (what is actually installed):

\`\`\`text
$TOOLS_CHECK
\`\`\`

\`idf_tools.py list\` (what \`tools/tools.json\` in the pinned tree recommends):

\`\`\`text
$TOOLS_LIST
\`\`\`
$END
BLK
)"

# Splice the block between the markers, preserving everything else byte-for-byte.
# (ENVIRON, not -v: awk -v would reinterpret backslash escapes inside the block.)
NEW="$(ENV_BEGIN="$BEGIN" ENV_END="$END" ENV_BLOCK="$BLOCK" awk '
  $0 == ENVIRON["ENV_BEGIN"] { print ENVIRON["ENV_BLOCK"]; skipping = 1; next }
  $0 == ENVIRON["ENV_END"]   { skipping = 0; next }
  !skipping                  { print }
' "$OUT")"

if [ "$CHECK" -eq 1 ]; then
  # Compare only the machine-invariant rows (header comment); `|| true` because
  # grep exits 1 on no match and a template full of TBD must still diff cleanly.
  OLD_INV="$(grep -E "$INVARIANT_ROWS" "$OUT" || true)"
  NEW_INV="$(printf '%s\n' "$NEW" | grep -E "$INVARIANT_ROWS" || true)"
  if [ "$OLD_INV" = "$NEW_INV" ]; then
    echo "env.lock.md invariant rows are up to date"; exit 0
  else
    echo "env.lock.md is STALE in a machine-invariant row — run tools/env-lock.sh and commit the result" >&2
    diff -u <(printf '%s\n' "$OLD_INV") <(printf '%s\n' "$NEW_INV") | sed 's/^/  /' >&2 || true
    exit 1
  fi
fi
printf '%s\n' "$NEW" > "$OUT"
echo "wrote $OUT"
