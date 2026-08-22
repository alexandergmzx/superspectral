# ESP-IDF environment setup — step by step

**Decision:** ESP-IDF **v6.0.2** (tag + recorded commit SHA), installed by a manual full clone into `~/esp/idf/v6.0.2` with a private tools root `~/esp/tools/v6.0.2`, activated **only** through the committed [`.envrc`](../../.envrc) (direnv). No EIM, no VS Code extension, no `.bashrc` sourcing, no Arduino in any phase. Rationale and rejected alternatives: [ADR 0001](../adr/0001-toolchain-esp-idf-v6-pinned-environment.md). Evidence: bibliography [11](../bibliography/11-esp-idf-platform-and-toolchain.md).

**Trade-off:** two committed lines (`IDF_PATH`, `IDF_TOOLS_PATH`) reproduce the whole environment on CI and on a new laptop, and delete with one `rm -rf`; the price is that *you* track upgrades (see [upgrade-procedure.md](upgrade-procedure.md)) instead of an installer doing it for you. That is the point — an installer moved the goalposts twice in 15 months on this very host (§0).

This document is executed in roadmap phase **E1** (user present; it changes system state and the last step deletes ~19 GB). Every version number below was verified on **2026-08-20**. Time budget: ~2 h including the 30-minute gate build, excluding downloads.

---

## 0. Host audit — what is already on this machine (read-only, 2026-08-20)

Read before typing anything: three of the catalogued [pitfalls](pitfalls.md) are already staged here.

| Item | Observed | Consequence |
|---|---|---|
| OS | Linux Mint 22.3 (`ID_LIKE="ubuntu debian"`, Ubuntu 24.04 base); glibc 2.39 | apt names from the IDF Linux guide apply verbatim; QEMU's glibc ≥ 2.31 requirement is met |
| `python3` | 3.12.3, **resolves through `/usr/local/bin/python3`**, a root-owned symlink (2025-05-29) next to a disabled hand-built `python3.12.disabled` | every existing IDF venv records `home = /usr/local/bin` — a dangling-symlink time bomb ([A6](pitfalls.md#a-host-toolchain-shell)). Step 3 forces `/usr/bin` |
| `cmake` / `ninja` on PATH | **`/opt/st/stm32cubeclt_1.20.0/…`** 3.28.1 / 1.11.1 shadow `/usr/bin/cmake` 3.28.3 | both satisfy v6.0's ≥ 3.22, but `.envrc` puts `/usr/bin` first so the build never depends on ST's layout ([A15](pitfalls.md#a-host-toolchain-shell)) |
| `~/.bashrc` | `alias get_idf='. $HOME/esp/esp-idf/export.sh'` → a **v5.5-dev master snapshot**; `source /opt/ros/jazzy/setup.bash` **unconditionally** (line numbers at audit time: 235 and 462); `eval "$(direnv hook bash)"` present | ROS leaks `PYTHONPATH`, `CMAKE_PREFIX_PATH`, `LD_LIBRARY_PATH`, `AMENT_PREFIX_PATH` into every shell ([A1](pitfalls.md#a-host-toolchain-shell), [A2](pitfalls.md#a-host-toolchain-shell)); the alias is a habit trap ([A3](pitfalls.md#a-host-toolchain-shell)); direnv is ready |
| IDF trees | `~/esp/esp-idf` (master snapshot), `~/esp/v5.4.1`, `~/.espressif/v6.0.1` (EIM 0.12.3), plus `~/esp/ESP8266_RTOS_SDK`, `~/esp/xtensa-lx106-elf` | **~19 GB**, three generations of metadata, two registries (`esp_idf.json` vs `tools/eim_idf.json`). **Installed is v6.0.1, not the pinned v6.0.2** (critic A7). Deleted in step 9, not before |
| `~/.espressif/tools/activate_idf_v6.0.1.sh` | exports `IDF_COMPONENT_LOCAL_STORAGE_URL=file:///home/alexmint/.espressif/tools`; `~/.espressif/tools/components/` holds a **partial** mirror (lvgl 9.2.0–9.4.0, no esp-dsp) | silent registry short-circuit ([B8](pitfalls.md#b-build-system-and-configuration)); `.envrc` unsets it |
| Constraints files | `~/.espressif/espidf.constraints.v6.0.txt` (2025-05-28, pins esptool 4.9) **and** `~/.espressif/tools/espidf.constraints.v6.0.txt` (2026-05-21, esptool 5.3) | never cite a host copy; the URL is <https://dl.espressif.com/dl/esp-idf/espidf.constraints.v6.0.txt> ([A21](pitfalls.md#a-host-toolchain-shell)) |
| udev | 19 rule files. `60-openocd.rules` matches `303a:1001`/`1002` (`MODE="660" GROUP="plugdev" TAG+="uaccess"`); `99-platformio-udev.rules` matches `303a:1001` (`MODE="0666"`, ModemManager ignore); `98-openocd.rules` also present | **do not add a third rule that sets MODE/GROUP** for `303a:1001` — three-way race (critic A7). Step 4 adds a SYMLINK-only rule |
| groups | `dialout plugdev uucp docker …` | no `usermod` needed |
| ModemManager / brltty | masked / never installed (`un`) | nothing to fix ([E6](pitfalls.md#e-usb-serial-jtag-flashing-recovery), [E7](pitfalls.md#e-usb-serial-jtag-flashing-recovery)) |
| QEMU on disk | `esp_develop_9.0.0_20240606` | stale; a fresh `idf_tools.py install qemu-xtensa` in the new tools root is mandatory before any QEMU experiment (critic A7) |
| OpenOCD on disk | `v0.12.0-esp32-20260304` | fine; clears Zephyr's `20251215` floor for FreeRTOS awareness |
| esp-clang on disk | `esp-20.1.1_20250829` | validates the clang-format `v20.1.8` pin in [`.pre-commit-config.yaml`](../../.pre-commit-config.yaml) |
| VS Code | has `cpptools`; **no `espressif.esp-idf`** | keep it that way (§8) |
| `/dev/ttyACM*` | none at audit time (watch not connected) | the eFuse read is still outstanding — [first-flash-checklist.md](first-flash-checklist.md) |

## 1. Prerequisites

Verbatim from the v6.0.2 "Standard Toolchain Setup (Legacy)" page; all already satisfied on this host:

```bash
sudo apt-get install git wget flex bison gperf python3 python3-pip python3-venv \
    cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0
```

v6.0 requirements: **Python ≥ 3.10** (have 3.12.3), **CMake ≥ 3.22** (have 3.28.3 in `/usr/bin`), git, ~2 GB per tools root, space-free paths (`/home/alexmint/Development/Spectral` and `~/esp/idf/v6.0.2` qualify — [A17](pitfalls.md#a-host-toolchain-shell)).

## 2. Clone — full history, recursive, never shallow

```bash
mkdir -p ~/esp/idf
git clone -b v6.0.2 --recursive https://github.com/espressif/esp-idf.git ~/esp/idf/v6.0.2
cd ~/esp/idf/v6.0.2
git rev-parse HEAD      # goes into docs/devenv/env.lock.md (tools/env-lock.sh does it)
```

- `--recursive` is mandatory (~30 submodules: mbedtls, esp-phy blobs, cmock, unity, …).
- **Never `--depth 1` or `--shallow-submodules`**: `IDF_VER` (baked into the app descriptor, printed at boot) comes from `git describe`; a shallow tree yields a degraded string and some submodule remotes reject shallow fetches ([A10](pitfalls.md#a-host-toolchain-shell)).
- After **any** later `git checkout <tag>`: `git submodule update --init --recursive --jobs 8` ([A11](pitfalls.md#a-host-toolchain-shell)). Better: never switch tags in place — a new tree per version ([upgrade-procedure.md](upgrade-procedure.md)).

## 3. Install the tools into a private root

```bash
cd ~/esp/idf/v6.0.2

# 1. Private tools root — MUST be exported on its own line. The docs warn against
#    the prefix form `IDF_TOOLS_PATH=... ./install.sh` (pitfall A9).
export IDF_TOOLS_PATH="$HOME/esp/tools/v6.0.2"

# 2. Scrub the ROS 2 Jazzy environment injected by ~/.bashrc (pitfalls A1/A2).
unset PYTHONPATH CMAKE_PREFIX_PATH LD_LIBRARY_PATH AMENT_PREFIX_PATH

# 3. Force the distro interpreter. There is NO IDF_PYTHON override: tools/detect_python.sh
#    iterates python3 python python3.10 … on PATH and writes its pick into pyvenv.cfg
#    permanently (pitfall A7). PATH ordering is the only lever.
PATH=/usr/bin:$PATH ./install.sh esp32s3
```

`./install.sh esp32s3` installs one target's toolchain (~1.5 GB less than `all`; [A13](pitfalls.md#a-host-toolchain-shell)). Optional extras later: `./install.sh esp32s3 --enable-pytest --enable-ci`. QEMU: `python3 tools/idf_tools.py install qemu-xtensa` after `sudo apt-get install -y libgcrypt20 libglib2.0-0 libpixman-1-0 libsdl2-2.0-0 libslirp0` ([G8](pitfalls.md#g-testing-ci-emulation)).

Recovery rule for the venv, forever: `rm -rf "$IDF_TOOLS_PATH/python_env" && ./install.sh esp32s3`. The venv is a disposable cache; toolchains are unaffected. Never `pip install` into it by hand ([A8](pitfalls.md#a-host-toolchain-shell)).

Verify the interpreter choice before going on:

```bash
grep home "$IDF_TOOLS_PATH"/python_env/idf6.0_py3.12_env/pyvenv.cfg   # expect: home = /usr/bin
```

## 4. udev — a stable device name, nothing else

The watch enumerates as **`303a:821b`** while it runs the shipped Arduino/TinyUSB firmware and as **`303a:1001`** (the on-chip USB-Serial-JTAG) once a native IDF app without TinyUSB is flashed. `/dev/ttyACM*` numbering is enumeration-order dependent on a host with ST-Link, J-Link, Microchip and PlatformIO rules ([E8](pitfalls.md#e-usb-serial-jtag-flashing-recovery)).

**Add only a `SYMLINK+=` rule. Do not set `MODE`, `GROUP`, `OWNER` or `TAG`** — `60-openocd.rules` and `99-platformio-udev.rules` already match `303a:1001` with conflicting modes (`660 plugdev` vs `0666`); a third opinion makes the resulting permissions depend on rule-file ordering (critic A7). Your membership in `dialout` (the kernel default group for `ttyACM`) covers `303a:821b`, which no existing rule touches.

```bash
sudo tee /etc/udev/rules.d/99-twatch-s3.rules >/dev/null <<'RULES'
# Super Spectral — stable name for the LilyGO T-Watch S3. SYMLINK ONLY: permissions are
# already set by 60-openocd.rules / 99-platformio-udev.rules for 303a:1001; do not add
# MODE/GROUP here (three-way race). 821b = shipped Arduino TinyUSB CDC, 1001 = native USJ.
SUBSYSTEM=="tty", ATTRS{idVendor}=="303a", ATTRS{idProduct}=="821b", SYMLINK+="ttyTWATCH"
SUBSYSTEM=="tty", ATTRS{idVendor}=="303a", ATTRS{idProduct}=="1001", SYMLINK+="ttyTWATCH"
RULES
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Plug the watch in, then: `ls -l /dev/ttyTWATCH` and `udevadm info -q property -n /dev/ttyTWATCH | grep -E 'ID_VENDOR_ID|ID_MODEL_ID'`. If you ever own two watches, add `ATTRS{serial}=="…"` to the match. `ESPPORT=/dev/ttyTWATCH` is exported by `.envrc`.

## 5. direnv — the only activation path

```bash
cd ~/Development/Spectral
direnv allow            # once; re-run after every edit of .envrc
idf.py --version        # expect: ESP-IDF v6.0.2
echo "$IDF_PATH $IDF_TOOLS_PATH"
env | grep -E 'IDF_COMPONENT|PYTHONPATH|CMAKE_PREFIX_PATH|LD_LIBRARY_PATH|AMENT' ; echo "(expect nothing above)"
which cmake ninja python   # cmake → /usr/bin, ninja/python → the IDF tools root
```

What [`.envrc`](../../.envrc) does, in order: sets `IDF_PATH`/`IDF_TOOLS_PATH`; unsets the four ROS variables and `IDF_COMPONENT_LOCAL_STORAGE_URL`; prepends `/usr/bin`; exports `IDF_CCACHE_ENABLE=1`, `ESPPORT`, `ESPBAUD`; sources `export.sh`; asserts `idf.py --version` contains `v6.0.2`. `cd` out of the repo and all of it is restored — which is why no alias and no `.bashrc` sourcing exist ([A14](pitfalls.md#a-host-toolchain-shell)). `.direnv/` is gitignored.

## 6. The go/no-go gate — 30 minutes, before any feature code

The only thing that can invalidate the version decision: neither `esp-dsp` (`idf >=4.2`) nor `esp_lvgl_port` (`idf >=5.2`) declares an *upper* IDF bound, and v6.0's warnings-as-errors + gnu23 default is the classic third-party breakage point ([B11](pitfalls.md#b-build-system-and-configuration)).

```bash
mkdir -p "$HOME/tmp/idf60-gate" && cd "$HOME/tmp/idf60-gate"
idf.py create-project gate && cd gate
idf.py set-target esp32s3
idf.py add-dependency "espressif/esp-dsp==1.8.2"
idf.py add-dependency "espressif/esp_lvgl_port==2.9.0"
idf.py add-dependency "lvgl/lvgl==9.5.0"
idf.py add-dependency "espressif/esp_lcd_touch_ft5x06==1.1.1"
# In main/gate.c add, above app_main:
#   #include "driver/i2s_pdm.h"
#   #include "esp_lcd_panel_vendor.h"
#   #include "esp_dsp.h"
#   #include "lvgl.h"
idf.py build
grep -rl 'driver/i2c_master.h' managed_components/espressif__esp_lcd_touch_ft5x06/ && echo "ft5x06 uses the new I2C driver"
env | grep -c IDF_COMPONENT ; grep -E 'lvgl|esp-dsp' dependencies.lock   # 9.5.0 / 1.8.2, not 9.4.0 (pitfall B8)
```

| Outcome | Action |
|---|---|
| Builds | commit to v6.0.2; record the date and the four resolved versions in ADR 0001 and flip its status to **accepted** |
| A component refuses IDF 6 | record the exact error text in ADR 0001; fall back to **v5.5.5** (EOL 2028-01-21) in its own tree/tools root (`~/esp/idf/v5.5.5`, `~/esp/tools/v5.5.5`) by editing `IDF_VERSION_EXPECTED` in `.envrc`; schedule the v6.x migration for 2027. `CONFIG_COMPILER_DISABLE_DEFAULT_ERRORS=y` is a migration crutch only — never ship it |

## 7. First build of the skeleton, lock, inventory

```bash
cd ~/Development/Spectral/firmware/twatch-s3
idf.py set-target esp32s3          # regenerates sdkconfig from sdkconfig.defaults + sdkconfig.defaults.esp32s3
idf.py build
idf.py partition-table             # eyeball: ota_0 0x20000, ota_1 0x420000, coredump 0xFF1000, ends at 0x1000000
idf.py size
git add dependencies.lock          # the reproducibility keystone (pitfall B6); managed_components/ stays ignored
cd ~/Development/Spectral && tools/env-lock.sh && git add docs/devenv/env.lock.md
pre-commit run --all-files         # then: pre-commit run --hook-stage manual -a  (lock + gen_esp32part checks)
```

Build it a second time from clean (`idf.py fullclean && idf.py build`) and compare `sha256sum build/*.bin` — `CONFIG_APP_REPRODUCIBLE_BUILD=y` must make them identical on one machine ([B19](pitfalls.md#b-build-system-and-configuration)). Then un-`if: false` the firmware job in [`ci.yml`](../../.github/workflows/ci.yml) after re-deriving the container digest (`docker buildx imagetools inspect espressif/idf:v6.0.2 --format '{{println .Manifest.Digest}}'`).

**Do not flash yet.** Flashing is gated by [first-flash-checklist.md](first-flash-checklist.md) (backup, eFuse read, vendor table) — phase E2.

## 8. Editor — clangd downstream of the shell; no Espressif extension

`idf.py build`/`reconfigure` writes `firmware/twatch-s3/build/compile_commands.json`. The committed [`.clangd`](../../.clangd) points clangd at it and strips the GCC/Xtensa-only flags (`-mlongcalls`, `-fstrict-volatile-bitfields`, `-fno-tree-switch-conversion`) that make clangd refuse to index ([A20](pitfalls.md#a-host-toolchain-shell)).

Suggested **user-level** VS Code settings (not committed — the esp-clang path moves with the tools root):

```json
{
  "clangd.path": "${env:IDF_TOOLS_PATH}/tools/esp-clang/esp-20.1.1_20250829/esp-clang/bin/clangd",
  "clangd.arguments": [
    "--compile-commands-dir=${workspaceFolder}/firmware/twatch-s3/build",
    "--query-driver=${env:IDF_TOOLS_PATH}/tools/xtensa-esp-elf/**/bin/xtensa-esp32s3-elf-*",
    "--background-index",
    "--header-insertion=never"
  ],
  "C_Cpp.intelliSenseEngine": "disabled",
  "files.associations": { "*.h": "c" }
}
```

Launch VS Code from the direnv-activated shell (`code .`) so `${env:IDF_TOOLS_PATH}` resolves. Disable the MS IntelliSense engine or the two fight. **Do not install `espressif.esp-idf`**: v2.1.0 (2026-05) removed `idf.espIdfPath`/`idf.toolsPath` and discovers installations only through EIM's `eim_idf.json`; legacy setups "should still work to ease the transition" — an explicitly temporary promise ([A19](pitfalls.md#a-host-toolchain-shell)). For JTAG debugging use `idf.py openocd` + `idf.py gdb` (which also source `build/gdbinit/prefix_map` for reproducible-build path remapping) or a plain `cppdbg` config with `miDebuggerServerAddress: localhost:3333`.

## 9. Cleanup of the old state — only after steps 6–7 build and the first flash succeeds

**Order matters: prove the replacement, then delete.** Confirm each item with the user; none of it is source.

1. `~/.bashrc`: delete or repoint `alias get_idf` (→ master snapshot). Prefer deleting — direnv leaves no habitual command to get wrong.
2. `~/.bashrc`: wrap `source /opt/ros/jazzy/setup.bash` in a function (`ros_on() { source /opt/ros/jazzy/setup.bash; }`) so ROS is opt-in per shell. `.envrc` already defends the IDF shell, but every *other* Python tool on the machine benefits.
3. Remove the legacy trees: `rm -rf ~/.espressif ~/esp/esp-idf ~/esp/ESP8266_RTOS_SDK ~/esp/xtensa-lx106-elf`. `~/.espressif` is a classic `install.sh` root *and* EIM's parent with `IDF_TOOLS_PATH=~/.espressif/tools` nested inside it, five metadata files across three schema generations — `idf_tools.py uninstall` cannot untangle two layouts in one directory ([A5](pitfalls.md#a-host-toolchain-shell)). Deleting it also removes the stale constraints file and the partial component mirror, so [backup-policy.md](backup-policy.md) explicitly forbids carrying them forward. **`~/esp/v5.4.1` is excluded from this list on the owner's decision (2026-08-20): kept deliberately as a second reference environment, not superseded** — do not delete it as part of this step. **Done 2026-08-21:** `~/esp/esp-idf` (master snapshot) and the v5.5.5 tools root are gone; `~/.espressif` (the EIM tree, holding v6.0.1) and the ESP8266/xtensa-lx106 trees are still present and are the remaining scope of this step.
4. `ccache --max-size=10G` only while a second IDF tree (an upgrade candidate, or `v5.4.1` kept as a reference environment) is present. The v5.5.5 fallback root, evaluated during the ADR 0001 gate, is **not** kept installed (owner's decision, 2026-08-20) and was removed 2026-08-21 — install it on demand with the same two lines as §2.2–2.3, substituting the tag and tools root.
5. Re-run `tools/env-lock.sh` from a **fresh** shell and commit.

**E1 definition of done:** `idf.py --version` = v6.0.2 from a fresh shell inside the repo; `env | grep -E 'IDF_COMPONENT|PYTHONPATH'` empty; skeleton builds twice with identical `.bin` hashes; `dependencies.lock` + `env.lock.md` committed; ADR 0001 accepted; CI firmware job enabled; old trees gone — meaning the master snapshot and the v5.5.5 fallback (both done 2026-08-21), **not** `~/esp/v5.4.1`, which is a deliberate keep and not in scope of this gate.

## 10. Python environments that are not the IDF's

Three interpreters live on this machine and none of them is the other. Keeping
them apart is the same discipline `.envrc` applies to ESP-IDF.

| Environment | Where | What it is for | Licence |
|---|---|---|---|
| ESP-IDF venv | `~/esp/tools/v6.0.2/python_env/` | `idf.py`, `esptool`, `otatool` — created and owned by `install.sh`. **Never** used for repo scripts. | — |
| Host companion | `host/.venv`, from `host/pyproject.toml` + `host/uv.lock` + `host/.python-version` | parselmouth, numpy, scipy — the offline analysis and golden-file generation (`spectral-golden`) | **GPL-3.0-or-later** |
| Apache tooling, stdlib-only | system `python3` (3.12) | `doc_ocr`, `check_links.py`, `check_markers.py`, `check_presets.py`, `gen_colormap_lut.py` — no environment at all, by rule ([`python-scripts/README.md`](../../python-scripts/README.md) "Environment") | Apache-2.0 |
| Apache tooling with dependencies | one `uv` project **per package**: `python-scripts/synth_signals/.venv` and `python-scripts/golden_compare/.venv`, each from its own `pyproject.toml` + `uv.lock` + `.python-version` | `synth_signals` (numpy, scipy, pyyaml — the Tier-0 generator), `golden_compare` (numpy, pyyaml, mir_eval — the consumer of the golden files) | Apache-2.0 |

So there are **three `uv` projects** and three locks, and none of them shares a
`.venv` with another or with the IDF. The GPL side and the Apache side exchange
files on disk (`datasets/tier0-synthetic/*.wav` + `manifest.yaml` one way,
`host/golden/outputs/**` the other) and never import each other — the
`host-boundary` pre-commit hook and the `host` CI job grep for exactly that
([ADR 0004](../adr/0004-split-licensing.md)).

```sh
# GPL side -- host/.venv, gitignored
uv lock --check --project host                  # the lock still matches pyproject.toml
uv sync  --project host --frozen --extra dev
uv run   --project host python -c "import parselmouth; print(parselmouth.PRAAT_VERSION)"   # 6.1.38
uv run   --project host pytest -q host/tests
uv run   --project host spectral-golden verify

# Apache side -- one project per package, run from inside it
cd python-scripts/synth_signals && uv lock --check && uv sync --frozen --extra test && uv run pytest -q && cd -
cd python-scripts/golden_compare && uv lock --check && uv sync --frozen --extra test && uv run pytest -q && cd -

pipx install pre-commit                         # not `pip install --user`, not `uvx`
```

`uv` (0.11.32 here; CI installs the same version with `pip install uv==0.11.32`
and the inventory in `tools/env-lock.sh` records it) is used rather than bare
`venv` because the lock file is the artefact ADR 0009 needs:
`praat-parselmouth==0.4.7` pins Praat 6.1.38, and a resolver that silently moved
to a 0.5.x would change the default pitch method underneath every golden file.
`--frozen` installs the lock as committed; `uv lock --check` is what notices a
lock that no longer matches its `pyproject.toml`, which is why CI runs both.
`uvx pre-commit` would work for a one-shot run, but `pre-commit install` writes
the interpreter path into `.git/hooks/pre-commit`, so the tool has to stay on
PATH — hence pipx.

A shell with `PYTHONPATH` set (the ROS 2 leak `.envrc` strips for the IDF shell)
reaches into every one of these `.venv`s too: `uv run` honours `PYTHONPATH`, and
`/opt/ros/jazzy/lib/python3.12/site-packages` shadows the venv's own packages
at import time. Run the commands above from the direnv-activated repo shell, or
`env -u PYTHONPATH uv run …`.

## 11. Node and npm — the fourth environment (the host web application)

Added 2026-08-22 with [ADR 0021](../adr/0021-host-web-application.md) (roadmap
[W0](../roadmap/documentation-roadmap.md)). Section 10 keeps three Python
interpreters apart; this is a **fourth** environment that is not one of them and
must not become one.

| Tool | Version measured here (2026-08-22) | Path | Where the pin lives |
|---|---|---|---|
| node | `v20.20.2` | `/usr/bin/node` | `host/web/.nvmrc` (`20.20.2`) |
| npm | `10.8.2` | `/usr/bin/npm` | ships with node; not pinned separately |

Distribution packages, not `nvm` / `fnm` / `volta` — one Node on the machine, the
same way there is one `direnv`. `host/web/.nvmrc` is the single pin: the CI `web`
job reads it through `actions/setup-node`'s `node-version-file`, so the runner
and this machine cannot drift apart silently. `tools/env-lock.sh` records both
versions in the inventory (informational rows — the digest-pinned IDF container
carries no Node, so they are not in `INVARIANT_ROWS`).

The versions satisfy the toolchain's own floors, checked 2026-08-22:
vite 8.2.2 wants `^20.19.0 || >=22.12.0`, vitest 4.1.11 wants
`^20.0.0 || ^22.0.0 || >=24.0.0`, and TypeScript 7.0.2 — the native compiler —
answers `npx tsc --version` with `Version 7.0.2`.

**It never mixes with the three Python environments.** Node owns `host/web/` and
nothing else; no npm script shells into Python and nothing under `host/src/`
invokes npm. The front end and the backend meet over HTTP (`/api/...`) and, in a
built deployment, over one directory (`host/web/dist/`, mounted by uvicorn) —
never over an interpreter. The ROS 2 `PYTHONPATH` leak that section 10 warns
about does not reach Node at all, which is precisely why the two toolchains are
kept from calling each other: the day one does, the leak follows it.

### 11.1 `npm ci --ignore-scripts` is the only install path

```sh
cd host/web
npm ci --ignore-scripts --no-audit --no-fund   # the ONLY install command
node scripts/check-licences.mjs                # fail-closed licence gate (11.2)
npx tsc --noEmit                               # type-check, emits nothing
npx vitest run --project unit                  # unit project; `golden` arrives at W1
npm run build                                  # typecheck + vite build -> dist/
```

`npm ci` installs `package-lock.json` exactly and **refuses** when the lock and
`package.json` disagree; that refusal is the enforcing lock-vs-manifest check,
and it runs offline against the committed file in the CI `web` job. `npm install`
is for *changing* dependencies, and the way to do that without touching
`node_modules` is the manual-stage pre-commit hook
`web-lockfile-matches-manifest` (`npm install --package-lock-only
--ignore-scripts`, then `git diff --exit-code`), the npm twin of
`lockfile-matches-manifest` — manual because it needs the registry.

`--ignore-scripts` is deliberate and is the whole of the supply-chain mitigation
[ADR 0021](../adr/0021-host-web-application.md) names (its third `(−)`
consequence): a lifecycle script is arbitrary code from a transitive dependency,
running with your shell's privileges, on `npm ci`. If a package ever genuinely
needs its `postinstall`, the flag comes off **with the package named and the
reason stated** here and in [`ci.yml`](../../.github/workflows/ci.yml) — never
silently, and never as a fix for a build that "just fails".

### 11.2 The licence allowlist and its fail-closed gate

[ADR 0021](../adr/0021-host-web-application.md) decision 4 admits **MIT, ISC,
0BSD, BSD-2-Clause, BSD-3-Clause, Apache-2.0, CC0-1.0, Unlicense, BlueOak-1.0.0,
Python-2.0, Zlib and CC-BY-4.0** and nothing else. **AGPL-3.0 is forbidden** —
audioMotion-analyzer is the named do-not-use, because a served web application is
exactly the case its network clause reaches. GPL and LGPL npm packages are
refused too, not because this GPL tree could not carry them but so the allowlist
stays one line a reviewer can check.

The list is a **policy, and it is the owner's to sign** (roadmap W0's Owner
line), not something a lockfile update may widen. `node scripts/check-licences.mjs`
reads `package-lock.json` and **fails closed**: an unknown identifier, an absent
`license` field, or a licence expression it cannot evaluate is a failure, not a
warning. It runs locally (above) and as a named step of the CI `web` job, between
`npm ci` and the type-check, so a package can never reach `tsc` before its licence
has been read.

### 11.3 mkcert — phone-on-LAN (the owner's steps; **mkcert is not installed here**)

`navigator.mediaDevices` is `undefined` on an insecure origin that is not
`localhost`, so opening the analyzer on a phone over the LAN needs HTTPS
([ADR 0021](../adr/0021-host-web-application.md) decision 8). Phone-on-LAN is a
**requirement, not a nicety** (owner, 2026-08-22) and it is a W2 gate; Chrome's
insecure-origin flag is a development fallback and is deliberately not written
down here as the way in. `mkcert` is **absent from this machine as of
2026-08-22** — the steps below are the owner's to run, not a record of a run:

```sh
mkcert -install                                # local CA into this machine's trust stores
mkcert <lan-ip> localhost 127.0.0.1 ::1        # one certificate for the laptop's LAN address
# Keep BOTH files outside the repository. They are machine-local secrets: a
# certificate in the tree is a certificate in a push, and every third party who
# builds this mints their own.
spectral-web serve --host 0.0.0.0 \
    --ssl-certfile /path/outside/repo/<lan-ip>.pem \
    --ssl-keyfile  /path/outside/repo/<lan-ip>-key.pem
```

Then, on the phone: install `$(mkcert -CAROOT)/rootCA.pem` through the phone's
own certificate store — until that is done the phone rejects the certificate and
the live path never starts. **(verify on the actual phone)**: a laptop browser
already trusts the CA and proves nothing about the device the requirement is
about. The same recipe, from the GPL side's own point of view, is in
[`host/README.md`](../../host/README.md).

## Quick reference

| Need | Command |
|---|---|
| Activate | `cd ~/Development/Spectral` (direnv) |
| Build | `cd firmware/twatch-s3 && idf.py build` |
| Flash a dev build (ota_1, rollback armed) | `tools/flash.sh` — never `idf.py flash` ([flash.sh](../../tools/flash.sh)) |
| Monitor | `idf.py -p /dev/ttyTWATCH monitor` (exit with Ctrl-]) |
| Regenerate lock / inventory | `idf.py reconfigure` · `tools/env-lock.sh` |
| Install the web front end | `cd host/web && npm ci --ignore-scripts --no-audit --no-fund` (§11.1) |
| Serve the web application | `uv run --project host spectral-web serve` (add `--ssl-*` for a phone, §11.3) |
| After editing `sdkconfig.defaults*` | `rm -f sdkconfig && idf.py reconfigure` ([B2](pitfalls.md#b-build-system-and-configuration)) |
| After changing IDF version/target | `idf.py fullclean` ([B3](pitfalls.md#b-build-system-and-configuration)) |
| Something is wrong with the port | [brick-runbook.md](brick-runbook.md) |
