#!/bin/bash
source .env

sed -i "s/localhost/$HOST/g" depi/memory-state-dump/main/1
docker exec -it depi-server /app/depi-example/reset-dolt.sh
docker stop depi-server
sed -i "s/$HOST/localhost/g" depi/memory-state-dump/main/1
docker start depi-server
sleep 1
docker exec -it depi-server python3 /usr/src/depi/client/cli_local.py -json /app/depi-example/memory-state-dump/main/1
