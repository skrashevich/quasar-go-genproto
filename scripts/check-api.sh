#!/bin/sh
# Compare every exported Go declaration against the original module.
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
temp=$(mktemp -d)
trap 'rm -rf "$temp"' EXIT
export GOWORK=off
git init --quiet "$temp/upstream"
git -C "$temp/upstream" fetch --quiet --depth=1 https://github.com/freequasar/quasar-go-genproto 2f85025877ff367b10bc6e93e089207b8fca9a46
git -C "$temp/upstream" checkout --quiet FETCH_HEAD
cd "$temp/upstream"
# The original bindings also compile with the fork's supported Go minimum.
go mod edit -go=1.23.0
# Reproduce the pinned descriptor baseline from the original generated code.
mkdir "$temp/upstream/descriptor-export"
cp "$root/scripts/testdata/export-descriptors.go" "$temp/upstream/descriptor-export/main.go"
{
  printf 'package main\nimport (\n'
  go list ./proto/... | sed 's/.*/_ "&"/'
  printf ')\n'
} > "$temp/upstream/descriptor-export/imports.go"
go run ./descriptor-export "$temp/original.pb"
cmp "$temp/original.pb" "$root/compatibility/freequasar.pb"
# Apply the permitted import-prefix migration to the reference API only.
# Embedded protobuf descriptors retain their original bytes.
python3 - <<'PYREF'
from pathlib import Path
for path in Path('proto').rglob('*.pb.go'):
    source = path.read_text()
    if 'import (' in source:
        header, tail = source.split('import (', 1)
        imports, body = tail.split('\n)', 1)
        imports = imports.replace('github.com/freequasar/quasar-go-genproto',
                                  'github.com/skrashevich/quasar-go-genproto')
        path.write_text(header + 'import (' + imports + '\n)' + body)
PYREF
go mod edit -module=github.com/skrashevich/quasar-go-genproto
# The exporter served only to verify provenance and uses the original imports.
rm -rf descriptor-export
apidiff -m -w "$temp/original.api" github.com/skrashevich/quasar-go-genproto
cd "$root"
apidiff -m -incompatible "$temp/original.api" github.com/skrashevich/quasar-go-genproto > "$temp/diff"
if [ -s "$temp/diff" ]; then
  cat "$temp/diff" >&2
  exit 1
fi
printf 'Verified the complete original Go API\n'
