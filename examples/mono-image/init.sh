#!/bin/bash
HOST=localhost
GIT_MONITOR_HOST=localhost
GSN_MONITOR_HOST=localhost
export USERNAME='demo'
export PASSWORD='123456'
BASIC_HEADER=$(echo -n "$USERNAME:$PASSWORD" | base64)
cd "$(dirname "$0")"
echo "Script running at $(pwd)"

mongod &
/usr/bin/entrypoint &

PORT_TO_CHECK=27017
source ensure_port.sh

for file in "webgme/dumps/webgme"/*.json; do
    collection_name=$(basename "$file" .json)
    mongoimport --db webgme_depi --collection "$collection_name" --file "$file" --drop
done

PORT_TO_CHECK=3000
source ensure_port.sh

su -c 'gitea admin user create --username $USERNAME --password $PASSWORD --email $USERNAME@mail.org' git

source push-git-repos.sh