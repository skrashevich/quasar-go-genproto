#!/bin/sh
# Export the original descriptors and retain its checkout for API comparison.
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
upstream=$1
output=$2
export GOWORK=off
git init --quiet "$upstream"
git -C "$upstream" fetch --quiet --depth=1 https://github.com/freequasar/quasar-go-genproto 2f85025877ff367b10bc6e93e089207b8fca9a46
git -C "$upstream" checkout --quiet FETCH_HEAD
cd "$upstream"
# The original bindings also compile with the fork's supported Go minimum.
go mod edit -go=1.23.0
mkdir descriptor-export
cp "$root/scripts/testdata/export-descriptors.go" descriptor-export/main.go
go list ./proto/... > descriptor-export/packages
{
  printf 'package main\nimport (\n'
  sed 's/.*/_ "&"/' descriptor-export/packages
  printf ')\n'
} > descriptor-export/imports.go
go run ./descriptor-export "$output"
rm -rf descriptor-export
