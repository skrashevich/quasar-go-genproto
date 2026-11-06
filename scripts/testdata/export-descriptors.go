package main

import (
	"cmp"
	"os"
	"slices"

	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/reflect/protodesc"
	"google.golang.org/protobuf/reflect/protoreflect"
	"google.golang.org/protobuf/reflect/protoregistry"
	"google.golang.org/protobuf/types/descriptorpb"
)

func main() {
	var descriptors descriptorpb.FileDescriptorSet
	protoregistry.GlobalFiles.RangeFiles(func(file protoreflect.FileDescriptor) bool {
		descriptors.File = append(descriptors.File, protodesc.ToFileDescriptorProto(file))
		return true
	})
	slices.SortFunc(descriptors.File, func(a, b *descriptorpb.FileDescriptorProto) int {
		return cmp.Compare(a.GetName(), b.GetName())
	})
	data, err := (proto.MarshalOptions{Deterministic: true}).Marshal(&descriptors)
	if err != nil {
		panic(err)
	}
	if err := os.WriteFile(os.Args[1], data, 0644); err != nil {
		panic(err)
	}
}
