#!/bin/sh
dolt config --global -add user.email depi@vanderbilt.edu
dolt config --global -add user.name Depi
dolt sql-server -H 0.0.0.0 &
DOLT_PID=$!
sleep 1
dolt sql -f /var/lib/dolt/depi-example/depi_mysql.sql
wait $DOLT_PID
