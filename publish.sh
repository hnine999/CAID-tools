#!/bin/bash

# git clone git@git.isis.vanderbilt.edu:aa-caid/caid-tools.git
# cd caid-tools
# git tag -> to check latest tag
# ./publish.sh x.y.x

git submodule update --init

if [ -z "$1" ]; then
    echo "Error: Pass version number x.x.x as argument!"
    exit 1
fi

version=$1

# Start out by creating a branch at the currently checked out commit (typically HEAD of main)
git checkout -b "release-tmp-$version"

# Convert sub-modules to regular git folders
submodules=(
  "depi-impl"
  "gsn-domain"
  "webgme-depi"
)

for submodule in "${submodules[@]}"; do
  git rm --cached "$submodule"
  rm -rf "$submodule/.git"
  git add "$submodule"
done

rm ".gitmodules"

# Read the file containing the list of files to delete (make sure to end with a line-break in the black_list_files.txt)
while read -r file; do
    if [ -e "$file" ]; then
        echo "Deleting file: $file"
        rm "$file"
    else
        echo "File not found: $file"
    fi
done < "black_list_files.txt"

rm "black_list_files.txt"

git add .

git commit -m "converted commit"

# Then set the remote to the public github repo and fetch the last published version (main)
git remote set-url origin git@github.com:vu-isis/CAID-tools.git
git fetch --all

# Create a diff from the new release state with the last published version (main in github)
git diff -R --binary "release-tmp-$version" origin/main > release.diff

# Create temporary branch from that main and apply that diff
git checkout -b "new-release-$version" origin/main
git apply release.diff
git add .

git commit -am "Release ${version}"
# Finally push that new version to the remote
git push -u origin "new-release-$version":main