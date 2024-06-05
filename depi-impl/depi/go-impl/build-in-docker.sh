#!/bin/sh
cd /usr/src/depi/go-impl
mkdir -p build
#cd depi_grpc
#./get_grpc_docker.sh
#./compile_go_docker.sh
#cd ..
go build -o build/depiserver cmd/server/main.go
cp build/depiserver /build
