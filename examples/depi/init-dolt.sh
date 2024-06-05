#!/bin/sh

mysql -h dolt-server -u root -P 3306 < /app/depi-example/depi_mysql.sql
