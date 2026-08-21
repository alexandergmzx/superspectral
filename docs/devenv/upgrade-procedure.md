# ESP-IDF upgrade procedure

**Decision:** an ESP-IDF upgrade is a *new tree plus a new tools root*, built side by side with the current one, proven on hardware, and landed as **one reviewed commit** that bumps `.envrc`, the CI container digest, `dependencies.lock` and `env.lock.md` together. Never `git checkout <newtag>` in place (critic B3).

**Trade-off:** ~2 GB of disk and an afternoon per hop, in exchange for a bisectable, revertible upgrade and a guaranteed escape hatch (the old tree stays for one release cycle).

## When to upgrade — and when not to

| Trigger | Action | Why |
|---|---|---|
| Patch release on the pinned minor (v6.0.3 scheduled 2026-09-10, v6.0.4 2026-11-18) | run this procedure; low risk, same `sdkconfig.rename` set | bugfix-only by policy ("Service" period until 2027-03-20) |
| v6.1 stable (rc1 shipped 2026-08-18; v6.1.1 scheduled 2026-09-03, v6.1.2 2026-10-22) | **wait for v6.1.1/v6.1.2**, then hop | buys ~6 months of runway (EOL ≈ 2029-Q1); a `.0` release is where third-party components break |
| v6.0 enters Maintenance (2027-03-20) | plan the hop within the quarter | Maintenance = high-severity and security fixes only, "not recommended for new projects" |
| EOL advisory for v6.0 (ahead of 2028-09-20) | must already be gone | <https://www.espressif.com/en/support/documents/advisories> — set a calendar reminder |
| Component bump (`esp-dsp`, `lvgl`, `esp_lvgl_port`, …) without an IDF change | steps 3, 5, 6 only; `idf.py update-dependencies` then review the lock diff like source | tilde pins admit patch updates only; a minor (lvgl 9.4 → 9.5) is a deliberate manifest edit |

Policy facts (verified 2026-08-20): no LTS line; every minor gets a flat 30 months from its own GA (12 Service + 18 Maintenance). Re-read `SUPPORT_POLICY.md` and the support-periods chart before every hop — bibliography [11 §A](../bibliography/11-esp-idf-platform-and-toolchain.md).

## The procedure

Worked for `v6.0.2 → v6.1.x`; substitute tags.

### 1. New tree, new tools root — never in place

```bash
git clone -b v6.1.x --recursive https://github.com/espressif/esp-idf.git ~/esp/idf/v6.1.x
cd ~/esp/idf/v6.1.x
export IDF_TOOLS_PATH="$HOME/esp/tools/v6.1.x"
unset PYTHONPATH CMAKE_PREFIX_PATH LD_LIBRARY_PATH AMENT_PREFIX_PATH
PATH=/usr/bin:$PATH ./install.sh esp32s3
```

Prepare the bump in a **git worktree**, so the main checkout keeps building on v6.0.2 throughout:

```bash
git -C ~/Development/Spectral worktree add ../Spectral-upgrade -b env/idf-v6.1.x
cd ~/Development/Spectral-upgrade
sed -i 's/^IDF_VERSION_EXPECTED=.*/IDF_VERSION_EXPECTED="v6.1.x"/' .envrc && direnv allow
idf.py --version        # v6.1.x here; still v6.0.2 in ~/Development/Spectral
```

The edited `.envrc` is the first hunk of the eventual bump commit (step 6); nothing else changes in the main checkout until then.

### 2. Read the migration surface before building

- `docs/en/migration-guides/release-6.x/6.1/` in the new tree (or the hosted migration guide for the target version).
- **`sdkconfig.rename*`** of every component (`find "$IDF_PATH/components" -name 'sdkconfig.rename*' -newer ~/esp/idf/v6.0.2/Kconfig`): a renamed symbol is silently translated, a *removed* one is silently dropped. Diff our `sdkconfig.defaults*` against the rename lists and rewrite them to the new names — never rely on the translation layer (the brownout symbols already went through one rename, `CONFIG_ESP32S3_BROWNOUT_DET_LVL_SEL_*` → `CONFIG_ESP_BROWNOUT_DET_LVL_SEL_*`; [pitfalls](pitfalls.md) C10).
- The upstream constraints file for the new minor (`https://dl.espressif.com/dl/esp-idf/espidf.constraints.v6.1.txt`): esptool/kconfig/component-manager majors drive the pre-commit pins and every runbook's command names.
- `tools/tools.json` of the new tree: compiler and clang versions. A new esp-clang major means a new `mirrors-clang-format` pin and a reformat commit ([pitfalls](pitfalls.md) B20).

### 3. Build the same commit on both trees

```bash
# old
cd ~/Development/Spectral/firmware/twatch-s3 && idf.py -B build_v602 fullclean build
# new (in the upgrade worktree, new shell)
idf.py -B build_v61x set-target esp32s3 && idf.py -B build_v61x build
```

Same `SDKCONFIG_DEFAULTS`, both from clean. If the new tree needs `CONFIG_COMPILER_DISABLE_DEFAULT_ERRORS=y` to get a third-party component through, that component is not ready — open an issue upstream, pin the old version, and stop here.

### 4. Size and behaviour diffs

```bash
python -m esp_idf_size --format text --diff build_v602/super_spectral.map build_v61x/super_spectral.map
idf.py -B build_v61x size --diff build_v602 --unify   # CURRENT − REFERENCE; positive = grew
```

- Run the `host-tests/` golden-vector suite on both (it does not depend on IDF, so this checks our own code did not change) and the **backend-agreement test** (esp-dsp vs reference FFT) on QEMU or target under the new tree; compare in dB at the tolerance in [`../validation/golden-files.md`](../validation/golden-files.md).
- Re-run the build-twice-and-diff: `sha256sum build_v61x/*.bin` after a second clean build.
- Regenerate the SBOM (`esp-idf-sbom create` + `check`) — a new IDF pulls new submodule versions and CVE status.

### 5. Hardware pass before the digest bump merges

With the new build flashed to **ota_1 via `tools/flash.sh`** (rollback armed; ota_0 golden image untouched):

1. Boot log shows the new `IDF_VER`, PSRAM 8 MB octal at 80 MHz, the boot guard, the five I²C addresses.
2. Display, touch, PDM capture, one full preset cycle, one recorded take, one USB re-plug.
3. `esp_ota_mark_app_valid_cancel_rollback()` reached; power-cycle twice; still on ota_1.
4. The [experiment 0002](../validation/experiments/) rollback + boot-guard race checks still pass on the new bootloader (the bootloader is rebuilt by the new IDF — it is part of what changed).

### 6. Land it as one commit, keep the old tree one cycle

In a single reviewed commit:

- `.envrc`: `IDF_VERSION_EXPECTED="v6.1.x"`.
- `.github/workflows/ci.yml`: new container index digest (`docker buildx imagetools inspect espressif/idf:v6.1.x --format '{{println .Manifest.Digest}}'`).
- `firmware/twatch-s3/dependencies.lock` (regenerated by the new component manager; review every line).
- `firmware/twatch-s3/sdkconfig.defaults*` rewritten to the new symbol names (step 2).
- `.pre-commit-config.yaml` pins if esptool/kconfig/clang majors moved.
- `docs/devenv/env.lock.md` regenerated by `tools/env-lock.sh` from the **new** shell.
- `CHANGELOG.md` entry and, if a decision changed, a new ADR (ADR 0001 is amended by reference, not rewritten).

Then `direnv allow`, confirm `idf.py --version`, and **keep `~/esp/idf/v6.0.2` + `~/esp/tools/v6.0.2` until the next release has shipped on the new tree**. Reverting is a one-line `.envrc` change plus `git revert` of the commit.

## Rollback of an upgrade

1. `git revert <bump-commit>`; `direnv allow`.
2. `idf.py fullclean` in every build dir that saw the new tree ([pitfalls](pitfalls.md) B3 — a stale `CMakeCache.txt` from another IDF is the classic failure).
3. Re-flash the previous release to ota_1 with `tools/flash.sh`; ota_0 never changed.

## Checklist

- [ ] New tree + new tools root; old tree untouched
- [ ] Migration guide and every `sdkconfig.rename*` read; `sdkconfig.defaults*` rewritten, not translated
- [ ] Builds clean on both trees without `COMPILER_DISABLE_DEFAULT_ERRORS`
- [ ] `size --diff --unify` reviewed; golden-vector and backend-agreement tests pass; build-twice hashes identical
- [ ] Hardware pass on ota_1 with rollback armed; experiment 0002 re-run
- [ ] One commit: `.envrc` + digest + lock + defaults + pre-commit pins + `env.lock.md` + CHANGELOG
- [ ] Old tree kept one cycle; calendar reminder for the next support-window event
