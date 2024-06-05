#!/bin/bash

# Define source and target directories
source_dir="/repos"
target_dir="/tmp/depi"

# Check if target directory is empty
if [ -z "$(ls -A $target_dir)" ]; then
   echo "Target directory is empty. Copying files from source directory..."
   cp -R $source_dir/* $target_dir
   chmod -R 777 $target_dir
else
   echo "Target directory is not empty."
fi
