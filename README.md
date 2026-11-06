# Quasar Go protobuf bindings

Go bindings for the Quasar schemas used by
[Quasar Bridge](https://github.com/skrashevich/quasar-bridge), generated from
[v3rt3p/quasar-protos](https://github.com/v3rt3p/quasar-protos).

The initial snapshot was imported from upstream commit
[`14217ab44835dc0b107ae27c710b27cb9329e1d2`](https://github.com/v3rt3p/quasar-protos/commit/14217ab44835dc0b107ae27c710b27cb9329e1d2).
It included 230 schemas across the packages Bridge uses and their transitive
imports. This repository maintains a selected subset of upstream. The current
revision, source file list, per-file SHA-256 hashes, root packages, and tool
versions are recorded in [`schemas/manifest.json`](schemas/manifest.json).
Source bytes are under `schemas/`; generated Go packages are under `proto/`.

The legacy SpeechKit websocket envelope,
`alice/cuttlefish/library/speechkit_proto/client_ws.proto`, was deleted upstream
in commit
[`560d8739a5586eb7d47715f4c3cb57c3638fa9b0`](https://github.com/v3rt3p/quasar-protos/commit/560d8739a5586eb7d47715f4c3cb57c3638fa9b0).
Bridge still uses it, so its exact schema is retained from commit
[`1044fbdfcd0c2d6d8a26681e31186d13fbb5aef6`](https://github.com/v3rt3p/quasar-protos/commit/1044fbdfcd0c2d6d8a26681e31186d13fbb5aef6).
This exception is explicit in `schemas/manifest.json` under `legacy_overrides`.

## Use in Go

Go 1.23 or later is required. Add the module at a version or commit you have
chosen:

```sh
go get github.com/skrashevich/quasar-go-genproto@VERSION
```

Import the generated packages using the original schema directory layout:

```go
import client "github.com/skrashevich/quasar-go-genproto/proto/alice/protos/api/alicekit/protocol/client"
```

Normal Go builds use the checked-in bindings and do not need protoc or access
to the schema repository. The only direct runtime dependency is
`google.golang.org/protobuf v1.36.12`.

## Reproduce the bindings

Install the complete
[protoc 36.1 distribution](https://github.com/protocolbuffers/protobuf/releases/tag/v36.1),
including its `include/` directory next to `bin/`. Put `protoc` on `PATH`, then
install the pinned Go generator and regenerate from the checked-in snapshot:

```sh
GOTOOLCHAIN=go1.27.0 go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.36.12
export PATH="$(go env GOPATH)/bin:$PATH"
python3 scripts/update-protos.py
python3 scripts/update-protos.py --check
go test ./...
go vet ./...
```

The script requires exactly protoc 36.1 and protoc-gen-go v1.36.12 built with
Go 1.27.0. The generator's build toolchain controls its embedded `go/format`,
so it must be pinned as well to reproduce the output bytes. The script checks
the plugin's build metadata with `go version -m`. This generation requirement
does not change the Go 1.23 minimum for using the generated packages.
Generation is offline and uses source-relative output paths and explicit Go import
mappings. Google well-known schemas come from protoc's includes and use the
official Go runtime packages. `--check` verifies source hashes and the exact
set and bytes of generated files, without changing the checkout. Executables
can be selected using `--protoc` and `--protoc-gen-go`.

## Update the source

Choose an exact full lowercase 40-character upstream Git SHA:

```sh
python3 scripts/update-protos.py --revision FULL_SHA
python3 scripts/update-protos.py --check
go test ./...
go vet ./...
```

The update fetches that commit and the pinned legacy commit, refreshes the
selected schema snapshot, and regenerates the bindings. Add
`--source-dir /path/to/quasar-protos` to read exact commits from a local Git
clone instead of fetching; uncommitted source changes are ignored. Root
packages are listed in `scripts/update-protos.py`.

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
