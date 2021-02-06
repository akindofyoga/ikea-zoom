package edu.cmu.cs.ikea.utils;

import com.google.protobuf.Any;

import edu.cmu.cs.ikea.Protos;

public class Protobuf {
    // Based on
    // https://github.com/protocolbuffers/protobuf/blob/master/src/google/protobuf/compiler/java/java_message.cc#L1387
    public static Any pack(Protos.ToServerExtras extras) {
        return Any.newBuilder()
                .setTypeUrl("type.googleapis.com/sandwich.ToServer")
                .setValue(extras.toByteString())
                .build();
    }
}
