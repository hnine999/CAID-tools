# docker build -t caid-tools .
# docker run --rm --name caid -p 3000:3000 -p 8888:8888 -p 5150:5150 caid-tools

# This in a multiple stage build and only the built go-resources will be used from this step.
FROM golang:1.22.2-bookworm
RUN apt update
RUN apt install -y protobuf-compiler

RUN mkdir /depi

COPY /depi-impl/depi/go-impl /depi/go-impl
COPY /depi-impl/depi/proto /depi/proto

WORKDIR /depi/go-impl

RUN go get go-impl/server
RUN go get github.com/golang/protobuf/proto@v1.5.3
RUN go get go-impl/depi_grpc
RUN go build -o depiserver cmd/server/main.go

# This base image uses alpine
# NAME="Alpine Linux"
# VERSION_ID=3.18.6
# PRETTY_NAME="Alpine Linux v3.18"
# HOME_URL="https://alpinelinux.org/"

# Which uses https://wiki.alpinelinux.org/wiki/Alpine_Package_Keeper instead of apt-get
FROM gitea/gitea:1.21

COPY --from=0 /depi /depi

# Make sure needed binary available at correct place for the go built binary to work
RUN apk update && apk add --no-cache supervisor libc6-compat gcompat

# gitea listening on port 3000
ENV GITEA__REPOSITORY__ENABLE_PUSH_CREATE_USER=true

# mongodb and mongorestore
RUN echo 'http://dl-cdn.alpinelinux.org/alpine/v3.9/main' >> /etc/apk/repositories
RUN echo 'http://dl-cdn.alpinelinux.org/alpine/v3.9/community' >> /etc/apk/repositories
RUN apk add mongodb mongodb-tools
RUN mkdir /data
RUN mkdir /data/db

# nodejs/npm
RUN apk add --update nodejs npm

# webgme listening on port 8888
RUN mkdir /webgme-depi
COPY ./webgme-depi/webgme-depi-components /webgme-depi
RUN npm --prefix /webgme-depi install

# python
RUN apk add --no-cache gcc g++ make libffi-dev musl-dev mysql-dev python3-dev py3-pip

# depi-monitors
COPY ./depi-impl/depi/monitors /depi/monitors
COPY ./depi-impl/depi/proto /depi/monitors/proto

WORKDIR /depi/monitors
RUN pip install .
WORKDIR /

# supervisor
RUN apk update && apk add --no-cache supervisor
COPY examples/mono-image/supervisord.conf /etc/supervisord.conf

## init data that can be moved in correct place before services are running
COPY examples/mono-image/app.ini /data/gitea/conf/app.ini
RUN mkdir -p /depi/go-impl/.state/main
COPY examples/depi/memory-state-dump/main/1 /depi/go-impl/.state/main/1

# init data inserted after services are running via script
RUN mkdir -p /depi-init-data/webgme
COPY examples/webgme/dumps /depi-init-data/webgme/dumps
COPY examples/repos /depi-init-data/repos
COPY examples/mono-image/init.sh /depi-init-data/init.sh
COPY examples/mono-image/ensure_port.sh /depi-init-data/ensure_port.sh
COPY examples/push-git-repos.sh /depi-init-data/push-git-repos.sh

RUN /depi-init-data/init.sh

# /depi-init-data can be removed

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]