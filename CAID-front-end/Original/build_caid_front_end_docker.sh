#!/bin/bash

docker_tag="caid-front-end:cpsvo"
cd "$(dirname "$0")" || exit 1

mkdir -p Context/Files
rm -rf Context/Files/*

cd Context || exit 1

cp ../../../examples/client/settings.json Files
cp ../../../examples/client/clone_repos.sh Files

docker_image=$(docker images --filter "reference=$docker_tag" --format "{{.Repository}}:{{.Tag}}")
if [ -n "$docker_image" ]; then
  docker image rm $docker_tag
fi

docker buildx build --no-cache --build-arg DEPI_IMPL="$DEPI_IMPL" --build-arg GSN_ASSURANCE="$GSN_ASSURANCE" \
       --build-arg WEBGME_DEPI="$WEBGME_DEPI" --build-arg theiaDocker="$theiaDocker" -t "$docker_tag" .
