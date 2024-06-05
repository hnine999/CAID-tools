#!/bin/bash
while true; do
  if nc -z 127.0.0.1 27017; then
    echo "Success! 27017 is open!"
    break
  else
    echo "Mongo not yet listening on 27017, sleeping 3s ..."
    sleep 3
  fi
done