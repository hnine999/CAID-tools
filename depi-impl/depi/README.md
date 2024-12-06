# DEPI

DEPendency Intermediator

## Development

### Starting the gRPC server

The `go-impl` directory contains the Go implementation of the DEPI gRPC server. Make sure you
have a recent version of Go installed (<https://go.dev/dl/>)

1. Cd to the `go-impl` directory
1. `./depiserver -config default_config.json` - Starts the sever.


### Starting the Depi CLI
1. Cd to the client directory
1. `source venv/bin/activate` - Activate the virtual environment
1. `python src/depi_client/depi_cli.py`

### Starting the Git Monitor
1. Cd to the monitors directory
1. `source venv/bin/activate` - Activate the virtual environment
1. `start_git_monitor.sh` - Run the git monitor (if `.` isn't in your path, do `./start_git_monitor.sh`)

### Setting up python3 and virtual env

Make sure you've got python >= 3.6 installed together with pip. Then install [virtualenv](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/) and create a `venv` for this project (this is done once per project).
You need to do this step inside these three project-directories: `server`, `client`, `monitors`.

1. `pip install virtualenv` - Install the python package ("globally").
1. `python3 -m virtualenv venv` - Create the virtual environment for this project.
1. `source venv/bin/activate` - Activate the virtual environment (for windows there is a .bat).
1. `which python` - Should point to `./venv/bin/python`.
1. `pip install .` - Installs the dependencies for this project.

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
