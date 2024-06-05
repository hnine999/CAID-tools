#!/bin/bash

# git clone git@git.isis.vanderbilt.edu:aa-caid/caid-tools.git
# cd caid-tools
# git submodule update --init
# ./publish.sh 1.0.0

if [ -z "$1" ]; then
    echo "Error: Pass version number x.x.x as argument!"
    exit 1
fi

version=$1

git checkout -b "release-tmp-$version"
git remote set-url origin git@github.com:vu-isis/CAID-tools.git

git fetch --all

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

# Read the file containing the list of files to delete (make sure to end with line-break)
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

# Create a diff from the release state with the already released main
git diff -R --binary "release-tmp-$version" origin/main > release.diff

# Create temporary branch from main 
git checkout -b "new-release-$version" origin/main
git apply release.diff
git add .

git commit -am "Release ${version}"
git push -u origin "new-release-$version":main