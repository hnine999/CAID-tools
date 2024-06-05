#!/bin/bash
source .env

docker exec -it mongo mongoimport --db webgme --collection "_users" --file "/dumps/webgme/_users.json" --drop
sudo sed -i "s/localhost/$WEBGME_MONITOR_HOST/g" webgme/dumps/webgme/_projects.json
docker exec -it mongo mongoimport --db webgme --collection "_projects" --file "/dumps/webgme/_projects.json" --drop
sudo sed -i "s/$WEBGME_MONITOR_HOST/localhost/g" webgme/dumps/webgme/_projects.json
docker exec -it mongo mongoimport --db webgme --collection "guest+TestProject" --file "/dumps/webgme/guest+TestProject.json" --drop