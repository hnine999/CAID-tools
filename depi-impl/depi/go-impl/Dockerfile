# docker build -t go-depi -f ./go-impl/Dockerfile .
#docker run -p 5150:5151 go-depi
FROM golang:1.22.2-bookworm

RUN apt update
RUN apt install -y default-mysql-client
RUN apt install -y protobuf-compiler
RUN apt install -y python3 python3-pip

RUN mkdir -p /usr/src/depi/go-impl

# copy app source
ADD ./go-impl /usr/src/depi/go-impl
ADD ./client /usr/src/depi/client
ADD ./proto /usr/src/depi/proto

WORKDIR /usr/src/depi/client
RUN pip install . --break-system-packages

WORKDIR /usr/src/depi/go-impl

RUN go get go-impl/server
RUN go get github.com/golang/protobuf/proto@v1.5.3
RUN go get go-impl/depi_grpc
RUN go build -o depiserver cmd/server/main.go

CMD ["/usr/src/depi/go-impl/depiserver", "-config", "depi_config.json"]
