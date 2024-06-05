#!/bin/bash
pushd repos
for archive in *.tar.gz ; do
    tar -xzvf "$archive"
    d="${archive%.tar.gz}"
    repo_name="${d%.git}"

    pushd "$d"
    echo "Current directory: $(pwd)"
    git config --global --add safe.directory $(pwd)
    git remote set-url origin http://$USERNAME:$PASSWORD@localhost:3000/$USERNAME/$repo_name.git
    git push --mirror origin

    if [ "$repo_name" = "gsn" ]; then
        hook_url="http://$GSN_MONITOR_HOST:3002/webhook"
    else
        hook_url="http://$GIT_MONITOR_HOST:3003/webhook"
    fi

    curl --location --request POST "http://localhost:3000/api/v1/repos/$USERNAME/$repo_name/hooks" \
        --header "Content-Type: application/json" \
        --header "Authorization: Basic $BASIC_HEADER" \
        --header "Content-Type: application/json" \
        --data-raw '{
            "active": true,
            "branch_filter": "main",
            "config": {
                "content_type": "json",
                "url": "'"$hook_url"'",
                "http_method": "post"
            },
            "events": ["push"],
            "type": "gitea"
        }'

    curl --location --request PATCH "http://localhost:3000/api/v1/repos/$USERNAME/$repo_name" \
        --header "Authorization: Basic $BASIC_HEADER" \
        --header 'Content-Type: application/json' \
        --data-raw '{
            "private": false
        }'
    popd
    rm -rf "$d"
done

popd