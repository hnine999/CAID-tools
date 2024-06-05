#!/bin/bash
while true; do
  if nc -z 127.0.0.1 $PORT_TO_CHECK; then
    echo "Success! $PORT_TO_CHECK is open!"
    break
  else
    echo "No process is listening on port $PORT_TO_CHECK, sleeping 3s ..."
    sleep 3
  fi
done