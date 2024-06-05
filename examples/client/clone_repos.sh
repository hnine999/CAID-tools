#!/bin/bash

# Run this script in a folder to where you would like to clone the repositories.
# Modify $HOST and $USERNAME as needed
HOST='localhost'
USERNAME='demo'

repos=("eval-results" "eval-scripts" "gsn" "src" "test-runs" "testdata")

for repo_name in "${repos[@]}"; do
    git clone http://$HOST:3000/$USERNAME/$repo_name.git
done