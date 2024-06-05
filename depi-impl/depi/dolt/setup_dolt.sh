#!/bin/sh
set -x

cd /dolt
./doltamd sql-server -u root &
DOLT_PID=$!
sleep 3

mysql -h localhost -u root -P 3306 --protocol=tcp < depi_mysql.sql

sleep 2
kill $DOLT_PID
