#!/bin/sh
GOPATH=/go GOROOT=/usr/local/go go install -v -n -a google.golang.org/protobuf/cmd/protoc-gen-go@latest
GOPATH=/go GOROOT=/usr/local/go go install -v -n -a google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
sleep 99999
