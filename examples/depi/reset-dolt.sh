#!/bin/sh
set -x
mysql -h dolt-server -u depiadmin --password=depiadmin -P 3306 < /app/depi-example/depi_mysql_reset.sql
