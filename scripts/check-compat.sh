#!/bin/sh
# Verify the checked-out sources, including uncommitted files.
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
temp=$(mktemp -d)
trap 'rm -rf "$temp"' EXIT
cd "$root"

export GOWORK=off
module=github.com/skrashevich/quasar-go-genproto
test "$(go list -m)" = "$module"
test "$(go list -m -f '{{.Version}}' google.golang.org/protobuf)" = v1.36.12
mkdir "$temp/client"
cd "$temp/client"
go mod init example.org/compat-client
go mod edit "-require=$module@v0.0.0" "-replace=$module=$root"
cp "$root/scripts/testdata/consumer_test.go" .
cp "$root/compatibility/freequasar.pb" .
# Force all original packages into one process so their init functions run.
go list -mod=mod "$module/proto/..." > packages
{
  printf 'package consumer\nimport (\n'
  sed 's/.*/_ "&"/' packages
  printf ')\n'
} > imports_test.go
go mod tidy
go test -count=1 .
