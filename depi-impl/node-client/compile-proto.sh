#!/usr/bin/env bash

OUT_DIR="./src/pbs"
TS_OUT_DIR="./src/pbs"
IN_DIR="../depi/proto"

CURRENT_DIR=$(pwd)
NPM_BIN="${CURRENT_DIR}/node_modules/.bin"

PROTOC="${NPM_BIN}/grpc_tools_node_protoc"
PROTOC_GEN_TS_PATH="${NPM_BIN}/protoc-gen-ts"
PROTOC_GEN_GRPC_PATH="${NPM_BIN}/grpc_tools_node_protoc_plugin"

$PROTOC \
    -I="$IN_DIR" \
    --plugin=protoc-gen-ts=$PROTOC_GEN_TS_PATH \
    --plugin=protoc-gen-grpc=$PROTOC_GEN_GRPC_PATH \
    --js_out=import_style=commonjs:$OUT_DIR \
    --grpc_out=grpc_js:$OUT_DIR \
    --ts_out=service=grpc-node,mode=grpc-js:$TS_OUT_DIR \
    "$IN_DIR"/*.proto