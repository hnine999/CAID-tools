# DEPI

DEPendency Intermediator Server

This is the Go implementation of the DEPI server, and is the
successor to the previous Python implementation.

## Building

You can run the `build.sh` script to compile the server, or just run:
```shell
go build -o depiserver cmd/server/main.go
```

## Running
The default DEPI configuration uses an in-memory database, and can
be started with the depi_config.json in this directory:

```shell
./depiserver -config depi_config.json
```

There is also a copy of the in-memory default configuration
in `depi_config_mem.json`. There is also a default Dolt database
implementation in `depi_config_dolt.json`.

## Creating the Dolt database
Instead of the in-memory database, DEPI can use the Dolt database <https://www.dolthub.com/>. The
`../scripts` directory contains a SQL script to initialize the DEPI Dolt database. 

Assuming that you have downloaded Dolt and it is running with its initial root user,
you can use a MySQL client to initialize it:

```shell
mysql -h 127.0.0.1 -P 3306 -u root < ../scripts/depi_mysql.depi_mysql
```

This will create depi and depiadmin accounts, along with the necessary
database tables for depi. You can then run the depi server using the `depi_config_dolt.json`
configuration.
