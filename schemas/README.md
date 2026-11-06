# Quasar schema snapshot

These files are unmodified source bytes from
[v3rt3p/quasar-protos](https://github.com/v3rt3p/quasar-protos).
`manifest.json` records the exact Git revision, per-file SHA-256 hashes,
tool versions (including the generator's Go build toolchain), and
the retained legacy schema revision.
`LICENSE.upstream` reproduces the upstream rights notice verbatim.

The snapshot includes every upstream `.proto` file outside `google/protobuf/`,
including top-level and reconstructed schemas. For standard Google schemas,
generation uses the protoc 36.1 distribution's includes and the official Go
runtime packages.

The legacy `alice/cuttlefish/library/speechkit_proto/client_ws.proto` is retained
from commit `1044fbdfcd0c2d6d8a26681e31186d13fbb5aef6`, because it was deleted
upstream in `560d8739a5586eb7d47715f4c3cb57c3638fa9b0` and remains in use by
Bridge. All other files come from the manifest's top-level `revision`.

See the repository README for reproduction and explicit update commands.
