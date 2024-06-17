# Examples
This is where the example models live. These are a combination of states from:
 - git repositories with source code and gsn-assurance models (see `./repos`)
 - system models from webgme in the form of exported mongo documents (`./webgme`)
 - finally an exported snapshot of the depi data-base itself (`./depi`) which groups and links the resources from the other tools together

## Building and Running the Example Models
In addition to the models this repository also contains the neccessary resources for building and/or running the example system using docker. If you are new to these tools and want to try out them quickly we recommend using the monolithic docker-images exaplined and referenced in the root of this repository. (Note that the utilities for building those images and the models states reside here.)

If you are further along and are considering hosting some of the services from this example and maybe integrate some of your own services (e.g. existing repositories at gitlab or github) - the `docker-compose.yml` is a good start. Below follows the steps needs to run it and initiate it with the state mentioned above.

Note that in order to access these docker images you'll need to request access at https://git.isis.vanderbilt.edu/. 

## Initial setup
Do these only the first time

1. Install docker and docker-compose (tested with `Docker version 25.0.3, build 4debf41`)
    - `https://docs.docker.com/engine/install/ubuntu/`
    
    - Consider adding the docker group and current user following the post installation (that way you don't need to sudo).

    - Double check your docker compose binary/argument by typing `docker-compose` and `docker compose`.

1. Setup folders 

    - Run `./setup.sh` 

    - This command sets the ownership of the data and config folders to the default `git` user in gitea

1. Start services
    - Edit the `HOST` env var in `.env` if you will access the services from a different host than `localhost` (which is the default).
    The value can either be a domain/alias or an IP address.

    -  Make sure you have a gitlab token for your gitlab user with read_registry access [personal_access_tokens](https://git.isis.vanderbilt.edu/-/user_settings/personal_access_tokens). Then login the docker client to git isis `docker login git.isis.vanderbilt.edu:5050 -u <userName>` and provide the token when prompted.

    - `docker compose up -d`

    - gitea available at http://localhost:3000, webgme at http://localhost:8888 and depi at http://localhost:5150 + at the configured `HOST`.

1. Create gitea user, git repos, webgme model and depi state.

    - Run `./create-user-repos.sh` 
    
    - Note: If you want a different username and password for gitea, edit the related lines at the top of the file - `create-user-repos.sh` before executing it.
    
    - To check gitea updates / logs run the command `docker logs gitea --follow`.  During initial setup, you get the message  `Starting new Web server: tcp:0.0.0.0:3000 on PID: 7` after gitea repos are setup. (takes ~30sec.)
    

1. To check that none of the services are down

    - `docker ps -a`


## Upgrading Services
Whenever there is an updated docker image pushed to one of the registries and the docker-compose.yml been updated
with that new version.
- make sure to pull new docker-compose file
  - `git pull`
- stop and remove containers (all data is persisted outside of the containers)
  - `docker compose down`
- start all services again using the new compose
  - `docker compose up -d`

To clear out all stopped containers and unused images. (Make sure all containers specified in the docker-compose are up and running before executing this.)
```
docker system prune -a
```

## Resetting state
If you want to start over and reset the state to the checked in one you can follow these steps. (Alternatively you could reclone the repository or wipe the unversioned files, and then follow the steps in initial setup.)
- stop and remove containers
  - `docker compose down`
- delete all saved data for the services
  - `./delete-all-data.sh`
- start all services again using the new compose
  - `docker compose up -d`
- Reintialize the data
  - `./create-user-repos.sh`

## Updating the checked in state
All application data (gitea repos, webgme models and depi state) is persisted outside of the containers but is gitignored.
To update the version controlled state you can export/dump the states by calling `./dump-state.sh`.

Client side
===============

### Check gitea access
- To ensure that the services at the server are reachable open a browser and navigate to `http://<HOST>:3000`, e.g. `http://localhost:3000`.
- Login using the username and password specified in `create-user-repos.sh`
- Click on explore and view the repos created, specifically navigate to the `gsn` repo and copy the clone url (http not ssh)
 and clone it on your client computer. The deafult user credentials are username: `demo` and password `123456`.
- If you want to clone all repositories you can copy one of [client/clone_repos.sh/ps](/client) and modify as instructed and execute.

### VSCode extensions

To interact with the depi-storage you need to install an extension for the type of tool you intend to use. This demo uses:
`git`, `git-gsn` and `webgme`. The `git` tool is supported as part of the Depi Manager extension (that the other extensions depend on).
First of all [download and install vscode >= 1.82](https://code.visualstudio.com/download).

Install the linked vscode-extensions by searching for their name in the extensions menu under market place in your vscode instance.

- Depi Browser
- WebGME Client
- GSN Editor
  - This extension requires java 8+ [for more details about this extenion click here.](../gsn-domain/gsn-vscode-xtext/vscode-extension-self-contained/README.md)

#### Settings
 - To edit the user settings JSON do `Ctrl/Cmd + Shift + P` and start typing `Open User Settings (JSON)`. Invoke the command and paste the following into the JSON file.


IMPORTANT! Replace `<HOST>` with the same host configured for the depi-services.

```
    ...
    "depi.url": "<HOST>:5150",
    "depi.user_name": "demo",
    "webgme-depi.urls": ["http://<HOST>:8888/"],
    "webgme-depi.enableDepi": true,
    "gsnGraph.enableDepi": true
    ...
```
# Acknowledgements
This work was supported by the DARPA Assured Autonomy program and Air Force Research Laboratory. Any opinions, findings, 
and conclusions or recommendations expressed in this material are those of the author(s) and do not necessarily reflect 
the views of DARPA or AFRL.

#### Contact
caid-dev@vanderbilt.edu