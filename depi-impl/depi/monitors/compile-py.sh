#!/bin/sh
python -m grpc_tools.protoc --python_out=src --pyi_out=src --grpc_python_out=src -I../proto ../proto/depi.proto
