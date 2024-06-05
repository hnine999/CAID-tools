# DEPI Client

DEPendency Intermediator Client

The Depi currently doesn't work on Python 3.12, at least on Windows, because
of some incompatibility in the Protobuf inplementation. It works on Python 3.10 and
3.11.

## Installing locally on Linux/MacOS

You can install the depi locally using the following commands:
1. `python -m venv venv`
1. `source venv/bin/activate` - Activate the virtual environment
1. `pip install .`

## Installing locally on Windows

You can install the depi locally using the following commands:
1. `python -m venv venv`
1. `.\venv\scripts\activate` - Activate the virtual environment
1. `pip install .`

## Starting the Client
After the install, there will be a depi-cli command available in the path. If the depi
is running with a default configuration on the same host, you can simply do:
`depi-cli`

### User and Password
To specify the Depi user name and password use `--user` and `--password`.

### Host and Port
If the Depi server is running on a different server, you can use the `--host` and `--port`
options to specify the host and port where the Depi is running.

### SSL
If the Depi server is using SSL, specify `--ssl` as an option. If the Depi's server
certificate is self-signed, you can specify a certificate to use to verify the
server's certificate filename with the `--cert` option (this is usually just the
server's self-signed certificate). If the server's certificate has a host name other
than the hostname it is running on, you can specify the host name to expect in the
server's certificate with `--ssl-target-name`.

## Data loading/dumping
The Depi CLI has some features to dump the depi contents to a file so it can be reloaded
into another Depi instance, and also to load either the dump file or a JSON file generated
by the in-memory version of the Depi.

To dump the depi contents to a file, do:
```shell
Depi Command-line. Type help or ? to list commands.

Depi> dump dumpfile.cli
```
The generated file is a Depi script that could be loaded with the `run` command, but
because the `run` sends each command to the Depi with a single GRPC call, it can
be a little slow to do a bulk load. Instead, use the `load` command which
batches the `add` and `link` commands into groups of 100 so they load much faster.


To bulk-load an in-memory Depi JSON file, you can use the `--json` option on the `depi-cli`
command-line:
```shell
depi-cli --json 5.json
```

