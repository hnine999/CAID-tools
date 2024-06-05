# CAID-tools
Depi is a suite of tools for tracking dependencies across different types of resources stored in different ways. At the core is the depi-server which provides a protocol over gRPC. For the supported tools there are user-interfaces implemented as vscode-extensions and adapter/monitors that report in updates to the stored resources. The currently supported tools are `git`, `git-gsn` and `webgme`.

- **depi-impl** contains the source code for the depi-server, git-monitor, git-gsn-monitor, depi-cli and the depi vscode extension
- **examples** contains example models and utility scripts for docker (both for docker compose and the monolithic container)
- **gsn-domain** contains the vscode extension together with LSP for the GSN Assurance grammar
- **webgme-depi** contains a vscode extension wrapping a webgme instance (and webgme components providing the interface between these two)

## Getting started

Start the back-end services first.
```
docker run --rm --name caid -p 3000:3000 -p 8888:8888 -p 5150:5150 git.isis.vanderbilt.edu:5050/aa-caid/caid-tools/caid-tools:0.1.7
```

Then the theia IDE with the extensions.
```
docker run --rm --name caid-fe -p 4000:4000 --network="host" git.isis.vanderbilt.edu:5050/aa-caid/caid-tools/caid-front-end:0.1.7
```

Once up and running go to: [http://localhost:4000](http://localhost:4000) using your browser (tested with Chrome).

### Using the UI

Start out by cloning all the git-repositories that are part of this example. From the terminal in the bottom of the screen invoke the `clone_repos.sh` script. 
![Clone Repositories](examples/images/01-clone-repos.png)
This system consists of a system-model modelled in webgme (where models are stored in a mongo-database), source code used by the blocks in the system-model, a few git-repositories with either test-scripts or generated data. Finally there is an assurance model modelled in GSN Assurance that is also stored under git (in the `ansr` folder in the `gsn` repository). However from a perspective of Depi, those files are managed slightly different than regular git files where instead of being treated as regular files - the models are interpreted as Abstract Semantic Graphs.

In Depi, these different types of artifacts or _Resources_ are referred to as _Tools_, here `webgme`, `git` and `git-gsn`. A _Tool_ needs to the very least provide an interface for adding new _Resources_ (linking them can be done via the Depi Blackboard UI) and a mechanism for reporting in updates in the _Resources_. An actual collection of _Resources_ from a _Tool_ is referred to as _Resource-Group_. In the case of `git` a _Resource-Group_ is a specific repository and the _Resources_ are either files or directories within that repository. To view the current state of the example system press `Ctrl/Cmd + Shift + P` and start typing `Depi: Blackboard` and select the command. This will prompt you for a password to log into depi - the password for the `demo`-user is `123456`.
![Blackboard Command](examples/images/depi-blackboard-cmd.png)

 In the picture below the different _Resource-Groups_ with their _Resources_ and _Links_ between them all expanded and displayed. The _Links_ are directionaly relationships are interpreted as "depends-on" (for example all resources of the `git-gsn` _Resource-Group_ `ansr` depends-on other _Resources_.)

![Resource Groups](examples/images/blackboard-resource-groups.png)

#### Reveal Resources
With _Resources_ added to Depi, it is possible to navigate (granted the _Tool_ supports) to the actual implementation of that resource. For example, by selecting the Vehicle in the `webgme` _Resource Group_. 
![WebGME Reveal](examples/images/depi-blackboard-webgme.png)
Expanding the side-menu (click the three lines to right-corner and then clicking the boxed arrow in the top right corner the Vehicle model is opened up in the WebGME model editor.
![WebGME Reveal](examples/images/webgme-model.png)
You can do the same thing for the git-based _Resources_ and if the repository is cloned locally it will open up the file in the vscode-editor (or expand and highlight the folder in the explorer).

#### Show evidence and dependency chain
With the `.gsn`-file opened in the editor presse `Ctrl/Cmd + Shift + P` and start typing `GSN: Graph View` and select the command. Expanded the tree and navigate to the `TestPlanner` solution node.
![GSN Graph View](examples/images/02-gsn-graph-view.png)

Click on the `Show Dependency Tree` Button under the `State` section and the Depi Manager UI will opened up in a new tab displaying the 
dependency chain of the evidences associated with this Solution node.
![Dependency Graph](examples/images/03-dependency-graph.png)

## Developers

### Creating a release

1. update the dependenies edit the `versions` file and run the `./update-sub-modules.sh`.
2. `git commit -am "Release x.x.x"`
3. `git push origin main`
4. `git tag vx.x.x`
5. `git push origin vx.x.x`

### Publishing a release
To be on the safe side, this requires you to clone a fresh copy of the repository.

1. `git clone git@git.isis.vanderbilt.edu:aa-caid/caid-tools.git`
2. `cd caid-tools`
3. `git submodule update --init`
4. `./publish x.x.x`

# Acknowledgements
This work was supported by the DARPA Assured Autonomy program and Air Force Research Laboratory. Any opinions, findings, 
and conclusions or recommendations expressed in this material are those of the author(s) and do not necessarily reflect 
the views of DARPA or AFRL.

#### Contact
caid-dev@vanderbilt.edu