# Quasar Go protobuf bindings

This module extends the original
[`freequasar/quasar-go-genproto`](https://github.com/freequasar/quasar-go-genproto/tree/2f85025877ff367b10bc6e93e089207b8fca9a46)
with Go bindings for all Quasar protobuf schemas in
[v3rt3p/quasar-protos](https://github.com/v3rt3p/quasar-protos), including
those used by [Quasar Bridge](https://github.com/skrashevich/quasar-bridge).
At upstream commit
[`14217ab44835dc0b107ae27c710b27cb9329e1d2`](https://github.com/v3rt3p/quasar-protos/commit/14217ab44835dc0b107ae27c710b27cb9329e1d2)
the source snapshot covers 860 upstream schemas and one retained legacy schema.
The generator combines these with the pinned original descriptors, producing
864 Go files in a single module. Original message fields, types, defaults,
JSON names, enum values and import paths take precedence. New declarations
and fields extend that contract. Details and provenance are in
[`compatibility/README.md`](compatibility/README.md).
Standard `google/protobuf/` imports use protoc's includes and the official
Go protobuf packages.

The upstream revision, source paths, per-file SHA-256 hashes, and tool versions
are recorded in [`schemas/manifest.json`](schemas/manifest.json). Source bytes
are under `schemas/` and generated Go packages are under `proto/`.

The legacy SpeechKit websocket envelope,
`alice/cuttlefish/library/speechkit_proto/client_ws.proto`, was deleted upstream
in commit
[`560d8739a5586eb7d47715f4c3cb57c3638fa9b0`](https://github.com/v3rt3p/quasar-protos/commit/560d8739a5586eb7d47715f4c3cb57c3638fa9b0).
Bridge still uses it, so its exact schema is retained from commit
[`1044fbdfcd0c2d6d8a26681e31186d13fbb5aef6`](https://github.com/v3rt3p/quasar-protos/commit/1044fbdfcd0c2d6d8a26681e31186d13fbb5aef6).
This exception is explicit in `schemas/manifest.json` under `legacy_overrides`.

## Use in Go

Go 1.23 or later is required. Add the module at a chosen version or commit:

```sh
go get github.com/skrashevich/quasar-go-genproto@VERSION
```

When migrating from freequasar, change the import prefix from
`github.com/freequasar/quasar-go-genproto` to
`github.com/skrashevich/quasar-go-genproto`. Package suffixes and the original
Go API are preserved, along with protobuf names, encoding and JSON behavior.

```go
import client "github.com/skrashevich/quasar-go-genproto/proto/alice/protos/api/alicekit/protocol/client"
```

Top-level schemas share the module's `proto` package. Under `reconstructed/`,
each schema has its own Go package at the schema path without the `.proto`
suffix. For example, `reconstructed/alice/protos/data/memory.proto` maps to
`github.com/skrashevich/quasar-go-genproto/proto/reconstructed/alice/protos/data/memory`.

Normal Go builds use the checked-in bindings and do not need protoc or access
to the schema repository. The only direct runtime dependency is
`google.golang.org/protobuf v1.36.12`.

## Reproduce the bindings

Install the complete
[protoc 36.1 distribution](https://github.com/protocolbuffers/protobuf/releases/tag/v36.1),
including its `include/` directory next to `bin/`. Put `protoc` on `PATH`, then
install the pinned Go generator and regenerate from the checked-in snapshot:

```sh
python3 -m pip install -r scripts/requirements.txt
GOTOOLCHAIN=go1.27.0 go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.36.12
export PATH="$(go env GOPATH)/bin:$PATH"
python3 scripts/update-protos.py
python3 scripts/update-protos.py --check
sh scripts/check-compat.sh
go test ./...
go vet ./...
```

The script requires exactly protoc 36.1 and protoc-gen-go v1.36.12 built with
Go 1.27.0. The generator's build toolchain controls its embedded `go/format`,
so it must be pinned as well to reproduce the output bytes. The script checks
the plugin's build metadata with `go version -m`. This generation requirement
does not change the Go 1.23 minimum for using the generated packages.
Generation fetches the pinned original Go module to export its descriptors and
uses explicit Go import mappings. Access to GitHub and the Go dependencies is
required for generation and compatibility checks. Google well-known
schemas come from protoc's includes and use the official Go runtime packages. `--check` verifies source hashes and the exact
set and bytes of generated files, without changing the checkout. Executables
can be selected using `--protoc` and `--protoc-gen-go`.

## Check the original Go API

The compatibility check exports descriptors from the pinned original commit,
loads every package in one external client and
compares all original descriptors, plus a legacy binary and ProtoJSON envelope.
CI also compares every exported Go declaration against the pinned original, accounting
for the module path change:

```sh
go install golang.org/x/exp/cmd/apidiff@v0.0.0-20260908205506-85c1c2202aba
sh scripts/check-api.sh
```

## Update the source

Choose an exact full lowercase 40-character upstream Git SHA:

```sh
python3 scripts/update-protos.py --revision FULL_SHA
python3 scripts/update-protos.py --check
sh scripts/check-compat.sh
go test ./...
go vet ./...
```

The update fetches that commit and the pinned legacy commit, refreshes the
full schema snapshot, and regenerates the bindings. Add
`--source-dir /path/to/quasar-protos` to read exact commits from a local Git
clone instead of fetching; uncommitted source changes are ignored.

The manual **Update schemas** GitHub Actions workflow takes the same exact
revision, regenerates and checks the result, then commits and pushes changes
to `main`. It does not create version tags; publish a chosen version after
reviewing the update. CI verifies regeneration, compilation, and vet checks
with pinned tools. A separate CI job compiles and tests all packages with
Go 1.23.0 to check the supported runtime minimum.

## Rights notice

[`LICENSE`](LICENSE) and `schemas/LICENSE.upstream` reproduce the upstream
rights notice verbatim. Upstream reserves all rights and grants no license to
the extracted or reconstructed definitions. No additional rights to those
definitions or their generated bindings are granted by this repository.
This project is not affiliated with or endorsed by Yandex.
