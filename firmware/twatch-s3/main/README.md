# main — application entry

The `main` component is kept deliberately tiny: [`app_main.c`](app_main.c) runs the **3 s anti-brick boot guard as its first statement** (ADR 0015), logs `esp_reset_reason()`, and will only ever *wire* the components together (task creation, core pinning). ESP-IDF makes `main` implicitly depend on every other component, so real logic here would hide dependency errors — it lives in [`../components/`](../components/README.md) instead.

| File | Role |
|---|---|
| [`app_main.c`](app_main.c) | Boot guard → reset reason → bring-up TODO list in the order of [`docs/hw/twatch-s3-pins.md`](../../../docs/hw/twatch-s3-pins.md) |
| [`Kconfig.projbuild`](Kconfig.projbuild) | `SPECTRAL_BOOT_GUARD_MS` (default 3000, floor 1000 — never reduced) · `SPECTRAL_DEV_SLEEP_ARMED` (default n) |
| [`idf_component.yml`](idf_component.yml) | Registry dependencies, tilde-pinned (ADR 0001); `dependencies.lock` is generated and committed in roadmap E1 |
| [`CMakeLists.txt`](CMakeLists.txt) | `idf_component_register` + the project warning set (`-Werror -Wshadow -Wconversion -Wdouble-promotion -Wformat=2 -Wvla`; `-Wundef` only on `spectral_core`, see the top-level README) |

Build and flash instructions: [`../README.md`](../README.md).
