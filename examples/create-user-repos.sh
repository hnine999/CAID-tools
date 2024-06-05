#!/bin/bash
source .env
USERNAME='demo'
PASSWORD='123456'
BASIC_HEADER=$(echo -n "$USERNAME:$PASSWORD" | base64)

source ./import-depi-dump.sh
source ./import-webgme-dump.sh

docker exec -it gitea bash -c \
'/usr/local/bin/gitea admin user create '\
' --username '$USERNAME\
' --password '$PASSWORD\
' --email '$USERNAME'@mail.org'\
' -c /etc/gitea/app.ini'

source ./push-git-repos.sh