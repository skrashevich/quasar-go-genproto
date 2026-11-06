#!/usr/bin/env python3
"""Regenerate the checked-in Quasar bindings, or explicitly update their source."""

import argparse
import hashlib
import io
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "schemas"
OUTPUT = ROOT / "proto"
REPOSITORY = "https://github.com/v3rt3p/quasar-protos"
GO_IMPORT = "github.com/skrashevich/quasar-go-genproto/proto"
PROTOC_VERSION = "libprotoc 36.1"
PLUGIN_VERSION = "protoc-gen-go v1.36.12"
LEGACY_PATH = "alice/cuttlefish/library/speechkit_proto/client_ws.proto"
LEGACY_REVISION = "1044fbdfcd0c2d6d8a26681e31186d13fbb5aef6"

# Packages used by Bridge, its tests, and the Kuyase control helper. Include all
# schemas in each package, then follow imports rather than compiling the full
# upstream tree (which also contains unrelated reconstructed definitions).
ROOT_DIRS = (
    "alice/cuttlefish/library/speechkit_proto",
    "alice/library/client/protos",
    "alice/megamind/protos/common",
    "alice/megamind/protos/common/subscription_state",
    "alice/protos/api/alicekit/common/device_state",
    "alice/protos/api/alicekit/common/environment_state",
    "alice/protos/api/alicekit/directives",
    "alice/protos/api/alicekit/events/alice_request",
    "alice/protos/api/alicekit/events/alice_response",
    "alice/protos/api/alicekit/events/asr_result",
    "alice/protos/api/alicekit/events/asr_result/common",
    "alice/protos/api/alicekit/events/cancel_request",
    "alice/protos/api/alicekit/events/capability_update_state",
    "alice/protos/api/alicekit/events/common/event_header",
    "alice/protos/api/alicekit/events/continue_request",
    "alice/protos/api/alicekit/events/input_start_ack",
    "alice/protos/api/alicekit/events/stream_control",
    "alice/protos/api/alicekit/events/tts_generate",
    "alice/protos/api/alicekit/events/tts_speak",
    "alice/protos/api/alicekit/protocol/client",
    "alice/protos/api/alicekit/protocol/server",
    "alice/protos/api/alicekit/streaming",
    "alice/protos/data/channel",
    "alice/protos/endpoint",
    "alice/protos/endpoint/capabilities/alice_pro",
    "alice/protos/endpoint/capabilities/audio_file_player",
    "alice/protos/endpoint/capabilities/brick",
)
IMPORT = re.compile(rb'^\s*import\s+(?:public\s+|weak\s+)?"([^"]+)"', re.MULTILINE)


def run(command):
    return subprocess.check_output(command)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def require_revision(revision):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("revision must be an exact, lowercase 40-character Git SHA")


def read_revision(source, revision):
    """Read committed bytes, ignoring a local checkout's uncommitted changes."""
    require_revision(revision)
    archive = run(["git", "-C", str(source), "archive", "--format=tar", revision])
    with tarfile.open(fileobj=io.BytesIO(archive)) as contents:
        return {
            entry.name: contents.extractfile(entry).read()
            for entry in contents
            if entry.isfile() and (entry.name.endswith(".proto") or entry.name == "LICENSE")
        }


def closure(schemas):
    selected = set()
    for directory in ROOT_DIRS:
        roots = {name for name in schemas if str(pathlib.PurePosixPath(name).parent) == directory}
        if not roots:
            raise ValueError(f"no schemas found for required package {directory}")
        selected.update(roots)
    pending = list(selected)
    while pending:
        name = pending.pop()
        for raw_import in IMPORT.findall(schemas[name]):
            imported = raw_import.decode("utf-8")
            if imported.startswith("google/protobuf/"):
                continue
            if imported not in schemas:
                raise ValueError(f"{name}: missing imported schema {imported}")
            if imported not in selected:
                selected.add(imported)
                pending.append(imported)
    return {name: schemas[name] for name in sorted(selected)}


def update_source(revision, source_dir, temporary):
    require_revision(revision)
    source = source_dir
    if source is None:
        source = temporary / "upstream.git"
        subprocess.run(["git", "init", "--quiet", "--bare", str(source)], check=True)
        for commit in sorted({revision, LEGACY_REVISION}):
            subprocess.run(
                ["git", "-C", str(source), "fetch", "--quiet", "--depth=1", REPOSITORY, commit],
                check=True,
            )
    upstream = read_revision(source, revision)
    legacy = read_revision(source, LEGACY_REVISION)
    # The legacy websocket envelope was deleted upstream. Keep its exact final
    # known source rather than retaining an otherwise stale generated module.
    upstream[LEGACY_PATH] = legacy[LEGACY_PATH]
    schemas = closure({name: data for name, data in upstream.items() if name.endswith(".proto")})
    license_bytes = upstream["LICENSE"]
    if legacy["LICENSE"] != license_bytes:
        raise ValueError("legacy and current upstream licenses differ; review before updating")
    manifest = {
        "repository": REPOSITORY,
        "revision": revision,
        "protoc": PROTOC_VERSION,
        "protoc_gen_go": PLUGIN_VERSION,
        "root_directories": list(ROOT_DIRS),
        "legacy_overrides": {
            LEGACY_PATH: {
                "revision": LEGACY_REVISION,
                "reason": "Legacy SpeechKit websocket envelope removed from the current upstream tree.",
            }
        },
        "license_sha256": sha256(license_bytes),
        "files": {name: sha256(data) for name, data in schemas.items()},
    }
    return schemas, license_bytes, manifest


def read_snapshot():
    manifest = json.loads((SNAPSHOT / "manifest.json").read_text())
    require_revision(manifest["revision"])
    if manifest["repository"] != REPOSITORY:
        raise ValueError("snapshot repository differs from the generator")
    if manifest["root_directories"] != list(ROOT_DIRS):
        raise ValueError("root packages changed; refresh the snapshot with --revision")
    if manifest["protoc"] != PROTOC_VERSION or manifest["protoc_gen_go"] != PLUGIN_VERSION:
        raise ValueError("snapshot tool versions differ from the generator")
    if manifest["legacy_overrides"][LEGACY_PATH]["revision"] != LEGACY_REVISION:
        raise ValueError("legacy schema revision differs from the generator")
    schemas = {path.relative_to(SNAPSHOT).as_posix(): path.read_bytes() for path in sorted(SNAPSHOT.rglob("*.proto"))}
    if {name: sha256(data) for name, data in schemas.items()} != manifest["files"]:
        raise ValueError("snapshot schema files or hashes differ from manifest.json")
    if set(closure(schemas)) != set(schemas):
        raise ValueError("snapshot contains schemas outside the required import closure")
    license_bytes = (SNAPSHOT / "LICENSE.upstream").read_bytes()
    if sha256(license_bytes) != manifest["license_sha256"]:
        raise ValueError("snapshot license hash differs from manifest.json")
    return schemas, license_bytes, manifest


def executable(name, expected):
    path = shutil.which(name)
    if not path:
        raise ValueError(f"{name} is unavailable; install {expected}")
    actual = run([path, "--version"]).decode().strip()
    if actual != expected:
        raise ValueError(f"{name}: expected {expected}, found {actual}")
    return pathlib.Path(path).resolve()


def generate(schemas, temporary, protoc_name, plugin_name):
    protoc = executable(protoc_name, PROTOC_VERSION)
    plugin = executable(plugin_name, PLUGIN_VERSION)
    includes = protoc.parent.parent / "include"
    if not (includes / "google/protobuf/descriptor.proto").is_file():
        raise ValueError(f"missing protoc well-known includes in {includes}; install the complete protoc distribution")
    source = temporary / "source"
    generated = temporary / "generated"
    source.mkdir()
    generated.mkdir()
    for name, data in schemas.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    command = [
        str(protoc), f"--proto_path={source}", f"--proto_path={includes}",
        f"--plugin=protoc-gen-go={plugin}", f"--go_out={generated}", "--go_opt=paths=source_relative",
    ]
    command.extend(
        f"--go_opt=M{name}={GO_IMPORT}/{pathlib.PurePosixPath(name).parent}"
        for name in schemas
    )
    # An argument file avoids platform command-line length limits. Every path
    # here is relative to the snapshot, so generated headers contain no temp paths.
    arguments = temporary / "protoc.args"
    arguments.write_text("\n".join(command[1:] + list(schemas)) + "\n")
    subprocess.run([str(protoc), "@" + str(arguments)], check=True)
    return {path.relative_to(generated).as_posix(): path.read_bytes() for path in generated.rglob("*.pb.go")}


def sync(directory, files, pattern):
    for path in directory.rglob(pattern):
        if path.relative_to(directory).as_posix() not in files:
            path.unlink()
    for name, data in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the snapshot and generated files without modifying them")
    parser.add_argument("--revision", help="explicitly refresh the snapshot from this full upstream Git SHA")
    parser.add_argument("--source-dir", type=pathlib.Path, help="read exact commits from this local Git repository instead of fetching")
    parser.add_argument("--protoc", default="protoc", help="protoc executable (must be 36.1)")
    parser.add_argument("--protoc-gen-go", default="protoc-gen-go", help="Go plugin executable (must be v1.36.12)")
    args = parser.parse_args()
    if args.check and args.revision:
        parser.error("--check and --revision cannot be combined")
    if args.source_dir and not args.revision:
        parser.error("--source-dir requires --revision")
    with tempfile.TemporaryDirectory(prefix="quasar-protos-") as name:
        temporary = pathlib.Path(name)
        if args.revision:
            schemas, license_bytes, manifest = update_source(args.revision, args.source_dir, temporary)
        else:
            schemas, license_bytes, manifest = read_snapshot()
        generated = generate(schemas, temporary, args.protoc, args.protoc_gen_go)
        if args.check:
            existing = {path.relative_to(OUTPUT).as_posix(): path.read_bytes() for path in OUTPUT.rglob("*.pb.go")}
            changed = sorted(name for name in set(existing) | set(generated) if existing.get(name) != generated.get(name))
            license_path = OUTPUT / "LICENSE.upstream"
            if not license_path.is_file() or license_path.read_bytes() != license_bytes:
                changed.append("LICENSE.upstream")
            if changed:
                raise ValueError("generated bindings differ; run scripts/update-protos.py:\n  " + "\n  ".join(changed))
        else:
            if args.revision:
                sync(SNAPSHOT, schemas, "*.proto")
                (SNAPSHOT / "LICENSE.upstream").write_bytes(license_bytes)
                (SNAPSHOT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            sync(OUTPUT, generated, "*.pb.go")
            (OUTPUT / "LICENSE.upstream").write_bytes(license_bytes)
        print(f"{'Verified' if args.check else 'Generated'} {len(generated)} Go files from {len(schemas)} schemas at {manifest['revision']}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(f"quasar proto generation failed: {error}")
