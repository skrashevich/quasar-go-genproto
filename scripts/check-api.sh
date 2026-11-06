#!/bin/sh
# Compare every exported Go declaration against the original module.
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
temp=$(mktemp -d)
trap 'rm -rf "$temp"' EXIT
export GOWORK=off
sh "$root/scripts/export-freequasar.sh" "$temp/upstream" "$temp/original.pb"
cd "$temp/upstream"
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
apidiff -m -w "$temp/original.api" github.com/skrashevich/quasar-go-genproto
cd "$root"
apidiff -m -incompatible "$temp/original.api" github.com/skrashevich/quasar-go-genproto > "$temp/diff"
if [ -s "$temp/diff" ]; then
  cat "$temp/diff" >&2
  exit 1
fi
printf 'Verified the complete original Go API\n'
