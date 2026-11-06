package consumer

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"reflect"
	"strings"
	"testing"

	client "github.com/skrashevich/quasar-go-genproto/proto/alice/protos/api/alicekit/protocol/client"
	"google.golang.org/protobuf/encoding/protojson"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/reflect/protodesc"
	"google.golang.org/protobuf/reflect/protoreflect"
	"google.golang.org/protobuf/reflect/protoregistry"
	"google.golang.org/protobuf/types/descriptorpb"
)

func TestFreequasarEnvelope(t *testing.T) {
	message := &client.TClientMessage{Message: &client.TClientMessage_Event{Event: &client.TClientMessage_TEvent{}}}
	registered, err := protoregistry.GlobalTypes.FindMessageByName("NAlice.NAliceApi.TClientMessage")
	if err != nil || registered != message.ProtoReflect().Type() {
		t.Fatalf("registered message type = %v, error = %v", registered, err)
	}
	wire, err := proto.Marshal(message)
	if err != nil || !bytes.Equal(wire, []byte{0x0a, 0x00}) {
		t.Fatalf("wire = %x, error = %v", wire, err)
	}
	data, err := protojson.Marshal(message)
	var compact bytes.Buffer
	if err != nil {
		t.Fatal(err)
	}
	if err := json.Compact(&compact, data); err != nil || compact.String() != `{"Event":{}}` {
		t.Fatalf("ProtoJSON = %s, error = %v", data, err)
	}
	var decoded client.TClientMessage
	if err := protojson.Unmarshal(data, &decoded); err != nil || !proto.Equal(message, &decoded) {
		t.Fatalf("decoded = %v, error = %v", &decoded, err)
	}
}

// Existing descriptor entries must retain their original order and values.
// Reservations can be consumed by newly extracted fields.
func checkDescriptor(t *testing.T, old, current protoreflect.Message, path string) {
	t.Helper()
	old.Range(func(field protoreflect.FieldDescriptor, value protoreflect.Value) bool {
		if field.Name() == "reserved_range" || field.Name() == "reserved_name" {
			return true
		}
		next := current.Get(field)
		name := path + "." + string(field.Name())
		if field.IsList() {
			previous, added := value.List(), next.List()
			if previous.Len() > added.Len() {
				t.Errorf("%s shortened", name)
				return true
			}
			for i := 0; i < previous.Len(); i++ {
				if field.Message() != nil {
					checkDescriptor(t, previous.Get(i).Message(), added.Get(i).Message(), fmt.Sprintf("%s[%d]", name, i))
				} else if !reflect.DeepEqual(previous.Get(i).Interface(), added.Get(i).Interface()) {
					t.Errorf("%s[%d] changed", name, i)
				}
			}
		} else if field.Message() != nil {
			checkDescriptor(t, value.Message(), next.Message(), name)
		} else if !reflect.DeepEqual(value.Interface(), next.Interface()) {
			t.Errorf("%s changed", name)
		}
		return true
	})
}

func TestLegacyDescriptors(t *testing.T) {
	data, err := os.ReadFile("freequasar.pb")
	if err != nil {
		t.Fatal(err)
	}
	var legacy descriptorpb.FileDescriptorSet
	if err := proto.Unmarshal(data, &legacy); err != nil {
		t.Fatal(err)
	}
	for _, file := range legacy.File {
		if strings.HasPrefix(file.GetName(), "google/protobuf/") {
			continue
		}
		current, err := protoregistry.GlobalFiles.FindFileByPath(file.GetName())
		if err != nil {
			t.Error(err)
			continue
		}
		// Go import paths change with the module name. Protobuf names and
		// all wire and JSON attributes retain the original contract.
		if file.Options != nil && file.Options.GoPackage != nil {
			renamed := strings.Replace(file.Options.GetGoPackage(), "github.com/freequasar/quasar-go-genproto", "github.com/skrashevich/quasar-go-genproto", 1)
			file.Options.GoPackage = &renamed
		}
		checkDescriptor(t, file.ProtoReflect(), protodesc.ToFileDescriptorProto(current).ProtoReflect(), file.GetName())
	}
}
