#!/bin/bash
USERNAME='demo'
PASSWORD='123456'

# Over write depi
main_depi_dir=depi/.state/main
latest_file=$(ls -t "$main_depi_dir" | head -n1)

if [ -n "$latest_file" ]; then
    cp "$main_depi_dir/$latest_file" depi/memory-state-dump/main/1
    sed -i "s/$HOST/localhost/g" depi/.state/main/1
else
    echo "No latest depi state file found."
fi

# Remove existing dump directory
docker exec -it mongo rm -rf /dumps/webgme
docker exec -it mongo mkdir /dumps/webgme

# Run mongodump to export the 'webgme' database
docker exec -it mongo mongoexport --uri="mongodb://127.0.0.1:27017/webgme"  --collection=_projects  --out=/dumps/webgme/_projects.json
docker exec -it mongo mongoexport --uri="mongodb://127.0.0.1:27017/webgme"  --collection=_tokenList  --out=/dumps/webgme/_tokenList.json
docker exec -it mongo mongoexport --uri="mongodb://127.0.0.1:27017/webgme"  --collection=_users  --out=/dumps/webgme/_users.json
docker exec -it mongo mongoexport --uri="mongodb://127.0.0.1:27017/webgme"  --collection=guest+TestProject  --out=/dumps/webgme/guest+TestProject.json

pushd repos
for archive in *.tar.gz ; do
    d="${archive%.tar.gz}"
    repo_name="${d%.git}"
    git clone --bare http://$USERNAME:$PASSWORD@localhost:3000/$USERNAME/$repo_name.git

    rm $archive
    tar -czvf "$archive" "$d"
    rm -rf "$d"
done

popd
