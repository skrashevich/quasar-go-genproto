# Original API baseline

`scripts/export-freequasar.sh` fetches `freequasar/quasar-go-genproto` at commit
[`2f85025877ff367b10bc6e93e089207b8fca9a46`](https://github.com/freequasar/quasar-go-genproto/tree/2f85025877ff367b10bc6e93e089207b8fca9a46)
and exports a deterministic `FileDescriptorSet` from every package using its
protobuf runtime v1.36.12. The temporary descriptor set has SHA-256
`be89f1219c50491cbb9e4e461cdccb40170bebbdf9f785c57e4cc78f7cfd4f67`
and contains 408 application file descriptors and seven Google runtime descriptors.

Generation and compatibility checks call this helper and require access to the
pinned upstream commit and its Go dependencies. The descriptor set preserves the
managed file options embedded in the original Go bindings and is created in a
temporary directory for each operation. `scripts/check-api.sh` also compares the
entire exported Go API from the fetched checkout with `apidiff`.

`scripts/update-protos.py` compiles the checked-in source snapshot to descriptors,
then `scripts/merge-descriptors.py` verifies the exported baseline hash and extends
it. Existing fields retain their numbers, names, Go types, oneofs, presence,
defaults and JSON names.
The Go module and descriptor `go_package` options use
`github.com/skrashevich/quasar-go-genproto`. The descriptor check accounts for
that prefix change. Protobuf package and message names retain their original
values. Original declarations keep their files and ordering. New fields and declarations
are appended. Old reservations are released where new fields occupy them.

For example, the merged API retains the original `QuasarMessage` fields,
`AppState.MediaInfo`, `TSpeechModeClientOptions`, and the original directive types.
An existing `TClientMessage.Event` writes `{"Event":{}}` in ProtoJSON. New fields
use the JSON names from the newer snapshot.

`ECredentialStatus` and `SoundFormat` retain their original descriptor files.
The new `SoundInfo` declaration is added to `remoting.proto`, alongside the
original `SoundFormat`, to keep the protobuf import graph acyclic. Its Go package
is the same as in the newer snapshot.

The original definitions win where newer extraction conflicts with the old API.
Future schema updates must pass both descriptor checks and the Go API comparison.
The upstream rights notice in the repository's `LICENSE` applies to this baseline.
