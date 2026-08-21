# Firmware

One target today: the LilyGO T-Watch S3 in [`twatch-s3/`](twatch-s3/README.md) (pure ESP-IDF v6.0.2, [ADR 0001](../docs/adr/0001-toolchain-esp-idf-v6-pinned-environment.md)). Additional targets — e.g. the native-Linux simulator target of ADR 0013 ([backlog](../docs/adr/README.md)) — would be sibling directories here, each with its own README; nothing outside `twatch-s3/` is compiled into the watch image.
