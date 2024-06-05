# DEPI

DEPendency Intermediator Server

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

If you don't already have a depi config file, use the `depi-config` command to get one:
`depi-config mem depi-config.json` to create a default config for the in-memory server
`depi-config dolt depi-config.json` to create a default config for dolt

Then run the server:
`depi-server -config depi-config.json` - Starts the server.

## Development
If you intend to do development on the Depi server code, use the following
instructions to set up your local environment.

### Starting the Depi server

Make sure you've got python and virtual env installed and initialized (see next section).

Do these steps once:

1. `python -m venv venv`
1. `source venv/bin/activate` - Activate the virtual environment
1. `./compile-py.sh`

You can also specify a config file on the command-line:
```bash
./run_local.py -config yourconfigfile
```

There are also default config files available:

```bash
./run_local -config-default-mem
```

```bash
./run_local -config-default-dolt
```

### Setting up python3 and virtual env

Make sure you've got python >= 3.6 installed together with pip. Then install [virtualenv](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/)
and create a `venv` for this project (this is done once). Perform these commands from the root-dir of this project (where this file is).
You need to do this step inside these three directories: `server`, `client`, `monitors`

1. `pip install virtualenv` - Install the python package ("globally").
1. `python3 -m virtualenv venv` - Create the virtual environment for this project.
1. `source venv/bin/activate` - Activate the virtual environment (for windows there is a .bat).
1. `which python` - Should point to `./venv/bin/python`.
1. `pip install -r requirements.txt` - Installs the dependencies for this project.

If pip install fails while installing `mysqlclient` follow instructions here https://pypi.org/project/mysqlclient/ for Ubuntu:

```commandline
sudo apt-get install python3-dev default-libmysqlclient-dev build-essential pkg-config
```

### Generating python classes from depi.proto

After modifying depi.proto the following command here and make sure to update the `../node-client` as well,
see [README.md](../node-client/README.md).

```commandline
./compile-py.sh
```

### Adding files from a repo

In addition to the VS Code plugin, you can use the Git adaptor to add files to
the depi. Just cd to a Git repo, you don't have to be in the root, you can be in a
subdirectory and it will find the root. Then run:

_depi_directory_ run*git.sh add \_your files here*

For example:
`../depi-impl/depi/run_git.sh add *.py`

If you want the resources to be added as local resources, where the Depi only
stores the absolute path for the files, then add the `--local` option before the add:

`../depi-impl/depi/run_git.sh --local add *.py`

It will also add resources as local if the Git repo does not have a remote URL.
The local resources should only be for testing and demos.

### Building a pip wheel file
