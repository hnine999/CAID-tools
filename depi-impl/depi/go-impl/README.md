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
mysql -h 127.0.0.1 -P 3306 -u root < ../scripts/depi_mysql.sql
```

This will create depi and depiadmin accounts, along with the necessary
database tables for depi. You can then run the depi server using the `depi_config_dolt.json`
configuration.

## Storage Details
The Depi currently has two options for data storage, although this can
be extended. One is an in-memory database that persists its data to disk
whenever a transaction is committed. It retains previous committed versions,
and also maintains separate directories for branches. The advantage of this
method is that it doesn't require a separate database process, and it is
easy to view the stored data as it is in JSON format.

The other data storage option is a database named Dolt <https://github.com/dolthub/dolt>.
Dolt provides a MySQL-compatible SQL interface, but layered on top of that
is a Git-like interface that allows branching. Queries and updates tend
to run faster in the Dolt database because of its caching and indexing
capabilities. It is also possible to view the data in the Dolt database
by connecting to it with a MySQL client, and accessing the `depi` database.

The Depi developers at Vanderbilt have used a hybrid approach with the
data storage, where we created an initial database using the in-memory
storage, and then used the last JSON file written in conjunction with the
Depi CLI tool to load that data into a Dolt version. This allowed us to
create a pre-populated example Dolt database very quickly.

### Setting up the In-Memory Database
There is very little setup work needed for the in-memory database. In the
Depi config JSON file, you just need to specify `memjson` as the database
type, and provide a directory name where the data will be stored.
For example:
```json
  "db": {
    "type": "memjson",
    "stateDir": ".state"
  },
```

### Setting up the Dolt Database
You need a Dolt executable, which can be downloaded from <https://github.com/dolthub/dolt>.
When you run Dolt for the first time, you need to tell it to allow a
default root user:
```shell
dolt sql-server -u root
```

You then run the `../scripts/depi_mysql.sql` script mentioned above. You
may want to edit it to change the default usernames and/or passwords.
After that, you can run dolt with:
```shell
dolt sql-server
```

By default, Dolt stores its data in a directory named `.dolt` in the directory
where it was started. You can change this with the `--data-dir` command-line option.
If you don't specify `--data-dir` you have to be careful to start Dolt in
the same directory each time.

Here are the default configuration options for the Depi server with a
Dolt database backend:
```json
  "db": {
    "type": "dolt",
    "host": "127.0.0.1",
    "port": 3306,
    "user": "depi",
    "password": "depi",
    "database": "depi"
  },
```

### Other Depi Configuration Sections
The Depi server currently has the following configuration sections:
- tools
- db
- logging
- audit
- server
- authorization
- users

#### tools

The `tools` configuration specifies options for various tools supposed by the Depi server.
Mainly, it needs to know the path separator used in URLs so it can figure out which
resources are "directories" (a resource URL that ends with a path separator is considered
a directory). Then when resources underneath a directory resource are modified, the directory
itself is considered to be modified. The default tool configuration looks like this:
```json
  "tools": {
    "git": { "pathSeparator": "/" },
    "webgme": { "pathSeparator": "/" },
    "git-gsn": { "pathSeparator": "/" }
  },
```

#### audit
The `audit` section specifies where audit logs are written. The default configuration is:
```json
  "audit": {
    "directory": "audit_logs"
  },

```

#### server
The `server` section specifies various settings for the Depi server. The default
configuration is:
```json
  "server": {
    "authorization_enabled": false,
    "default_timeout": 3600,
    "insecure_port": 5150,
    "secure_port": 0,
    "key_pem": "",
    "cert_pem": ""
  },

```

`authorization_enabled` indicates whether the Depi will do resource-group- and resource-level
access control on resources. If this is true, then the `authorization` section of the
config file is used to locate the definitions for authorization.

`default_timeout` specifies the number of seconds to wait before a user session times out.

`insecure_port` specifies the port number for unencrypted traffic. Set this to 0 to use SSL.

`secure_port` specifies the port number for encrypted traffic. Set this to 0 for unencrypted traffic.

`key_pem` specifies the name of a file containing the private key for SSL traffic.

`cert_pem` specifies the name of a file containing the certificate for the private key.

#### authorization

The `authorization` section specifies the name of a file that defines the various authorization
rules for resources, resource groups and links.

An authorization file contains rules that may be applied to various users in the
Depi's user configuration. A rule can contain other rules, and/or capabilities.
A capability specifies an action that a user may take. It may or may not take parameters
relevant to the capability. If it does take a parameter, then `*` can be used as a wildcard
for any parameter to allow any value.

These are the capabilities that can be configured:

The CapBranch* capabilities indicate whether a user may perform any branching-related action.
None of the CapBranch capabilities take any parameters.
`CapBranchCreate` indicates that a user may create a branch.
`CapBranchTag` indicates that a user may create a tag.
`CapBranchSwitch` indicates that a user may switch from one branch/tag to another.
`CapBranchList` indicates that a user may list the available branches.

The CapResGroup* capabilties indicate whether a user may perform certain actions on
resource groups. Each capability takes two parameters that restrict the set of
resource groups that the capability applies to. The first is the toolId,
the second is the resource group.
To specify that capability for all tools and resource groups, use * for each parameter.
`CapResGroupAdd` indicates that a user may add a resource group
`CapResGroupRead` indicates that a user may see the resources in a resource group
`CapResGroupChange` indicates that a user may change a resource group
`CapResGroupRemove` indicates that a user may remove a resource group

The CapResource* capabilities indicate whether a user may perform certain actions
on resources. Each capabilty takes three parameters that restrict the set of resources
that the capability applies to. The first is the toolId, the second is the resource group,
and the third is the resource.
To specify that capability for all tools, resource groups and resources, use * for each parameter.
`CapResourceAdd` 
`CapResourceRead` 
`CapResourceChange` 
`CapResourceRemove` 

The CapLink* capabilities indicate whether a user may perform certain actions
on links. Each capabilty takes six parameters that restrict the set of resources
that the capability applies to. The first is the from toolId, the second is the from resource group,
the third is the from resource, the fourth is the to toolId, the fifth is the to resource group,
and the sixth is the to resource..
To specify that capability for all tools, resource groups and resources, use * for each parameter.
`CapLinkAdd` 
`CapLinkRead` 
`CapLinkRemove` 
`CapLinkMarkClean` 

#### users
The `users` section specifies the Depi users. It specifies the user names, passwords, and
applicable authorization rules. The default configuration is:
```json
  "users": [
    { "name": "mark", "password": "mark", "auth_rules": ["all"] },
    { "name": "patrik", "password": "patrik", "auth_rules": ["all"] },
    { "name": "daniel", "password": "daniel", "auth_rules": ["all"] },
    { "name": "azhar", "password": "azhar", "auth_rules": ["all"] },
    { "name": "gabor", "password": "gabor", "auth_rules": ["all"] },
    { "name": "nag", "password": "nag", "auth_rules": ["all"] },
    { "name": "monitor", "password": "monitor", "auth_rules": ["all"] },
    { "name": "demo", "password": "123456", "auth_rules": ["all"] }
  ]
```

