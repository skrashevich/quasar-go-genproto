#!/usr/bin/env python3
"""Extend the pinned freequasar descriptors while retaining their public contract."""

import hashlib
import pathlib
import sys

from google.protobuf import descriptor_pb2 as pb


def read(path):
    return pb.FileDescriptorSet.FromString(pathlib.Path(path).read_bytes())


def extend_named(old, new, merge=None):
    by_name = {item.name: item for item in old}
    for item in new:
        if item.name not in by_name:
            old.add().CopyFrom(item)
        elif merge:
            merge(by_name[item.name], item)


def merge_enum(old, new):
    extend_named(old.value, new.value)
    # Added enum aliases require the corresponding descriptor option.
    if len({v.number for v in old.value}) != len(old.value):
        old.options.allow_alias = True


def merge_message(old, new):
    extend_named(old.oneof_decl, new.oneof_decl)
    oneofs = {item.name: i for i, item in enumerate(old.oneof_decl)}
    by_number = {item.number: item for item in old.field}
    by_name = {item.name: item for item in old.field}
    for field in new.field:
        if field.number in by_number or field.name in by_name:
            # Original type, number, presence, default, oneof and JSON name win.
            continue
        if field.label == pb.FieldDescriptorProto.LABEL_REQUIRED:
            raise ValueError(f"new required field {old.name}.{field.name}")
        added = old.field.add()
        added.CopyFrom(field)
        if field.HasField('oneof_index'):
            added.oneof_index = oneofs[new.oneof_decl[field.oneof_index].name]
    # Old reservations may have been reclaimed by newly extracted fields.
    numbers = {field.number for field in old.field}
    ranges = []
    for reserved in old.reserved_range:
        start = reserved.start
        for number in sorted(n for n in numbers if reserved.start <= n < reserved.end):
            if start < number:
                ranges.append(pb.DescriptorProto.ReservedRange(start=start, end=number))
            start = number + 1
        if start < reserved.end:
            ranges.append(pb.DescriptorProto.ReservedRange(start=start, end=reserved.end))
    del old.reserved_range[:]
    old.reserved_range.extend(ranges)
    names = [name for name in old.reserved_name if name not in {f.name for f in old.field}]
    del old.reserved_name[:]
    old.reserved_name.extend(names)
    extend_named(old.nested_type, new.nested_type, merge_message)
    extend_named(old.enum_type, new.enum_type, merge_enum)
    extend_named(old.extension, new.extension)


def merge_file(old, new):
    if old.package != new.package:
        raise ValueError(f"changed package in {old.name}")
    extend_named(old.message_type, new.message_type, merge_message)
    extend_named(old.enum_type, new.enum_type, merge_enum)
    extend_named(old.extension, new.extension)
    extend_named(old.service, new.service, lambda a, b: extend_named(a.method, b.method))


def declarations(file):
    def walk(scope, messages, enums):
        for enum in enums:
            yield scope + '.' + enum.name, enum
        for message in messages:
            name = scope + '.' + message.name
            yield name, message
            yield from walk(name, message.nested_type, message.enum_type)
    yield from walk('.' + file.package, file.message_type, file.enum_type)


def references(file):
    for _, declaration in declarations(file):
        if isinstance(declaration, pb.DescriptorProto):
            for field in list(declaration.field) + list(declaration.extension):
                yield field.type_name
                yield field.extendee
    for field in file.extension:
        yield field.type_name
        yield field.extendee
    for service in file.service:
        for method in service.method:
            yield method.input_type
            yield method.output_type


def main():
    expected = "be89f1219c50491cbb9e4e461cdccb40170bebbdf9f785c57e4cc78f7cfd4f67"
    if hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest() != expected:
        raise ValueError("freequasar compatibility baseline changed")
    legacy, latest = read(sys.argv[1]), read(sys.argv[2])
    files = {file.name: file for file in latest.file}
    owners = {name: file.name for file in legacy.file for name, _ in declarations(file)}
    # A moved declaration retains its old file and therefore its Go import path.
    for file in latest.file:
        for attribute in ('message_type', 'enum_type'):
            kept = [item for item in getattr(file, attribute)
                    if owners.get('.' + file.package + '.' + item.name, file.name) == file.name]
            del getattr(file, attribute)[:]
            getattr(file, attribute).extend(kept)
    for old in legacy.file:
        if old.name.startswith('google/protobuf/'):
            continue
        if old.name in files:
            merge_file(old, files[old.name])
        files[old.name] = old
    # SoundFormat lived in remoting.proto. Keep its new sibling there too,
    # otherwise model_objects -> remoting -> model_objects forms an import cycle.
    model = files['yandex_io/protos/model_objects.proto']
    remoting = files['yandex_io/protos/remoting.proto']
    sound_info = next((m for m in model.message_type if m.name == 'SoundInfo'), None)
    if sound_info is not None:
        remoting.message_type.add().CopyFrom(sound_info)
        kept = [m for m in model.message_type if m.name != 'SoundInfo']
        del model.message_type[:]
        model.message_type.extend(kept)
    owners = {name: file.name for file in files.values() for name, _ in declarations(file)}
    for file in files.values():
        # Keep original imports for custom options and add the owners of new types.
        dependencies = list(file.dependency)
        dependencies.extend(owners[name] for name in references(file)
                            if name in owners and owners[name] != file.name)
        original = list(file.dependency)
        del file.dependency[:]
        file.dependency.extend(dict.fromkeys(dependencies))
        # Existing imports keep their indices. Added dependencies are private.
        assert list(file.dependency[:len(original)]) == original
    result = pb.FileDescriptorSet(file=[files[name] for name in sorted(files)])
    pathlib.Path(sys.argv[3]).write_bytes(result.SerializeToString(deterministic=True))


if __name__ == '__main__':
    main()
