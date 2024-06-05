# Depi vscode extension
This is the main extension for Depi in vscode. In addition to providing the GUIs for viewing the resources and links in Depi and manage them via the Blackboard, it provides built-in functionality for handling resources for `git`.

To bring up the Blackboard press `Ctrl/Cmd + Shift + P` and start typing `Depi: Blackboard` and select the command. This will prompt you for a password to log into Depi as the configured user.

To add git resources, make a local clone of the repository of interest. (Note that this repostiory must also be configured to send webhook-events to the the git-monitor that reports in new versions of resources.) In the tree browser, right-click the file or folder you would like to to add to Depi and at the bottom of available commands click the `Add to Depi Blackboard`. This will add the resource to the Blackboard and open up the graphical editor. The newly added resources will appear highlighted with green untill the changes have been commited. Before committing you can connect it to other resources, but using the arrows around the box. These links are interpreted as the source **depends-on** the target.

## Externally callable commands
The GUIs can be initiated from by other extensions, see the list of commands defined in in the package.json or the listed commands under features.

## Edit config params for extension
To edit the user settings JSON do `Ctrl/Cmd + Shift + P` and start typing Open User Settings (JSON). Invoke the command and
configure the depi extension. Check `package.json` for available configurations.

```
    ...
    "depi.url": "127.0.0.1:5150",
    "depi.username": "<uname>",
    ...
```

## Developers

To debug the extension - open up `vscode-depi` in a vscode instance. The `.vscode` contains the launch settings for the
extension under `Run Extension`. First follow the steps below:

Install node-modules and compile.

```
npm install && npm run compile
```

While working on the extension use:

```
npm run watch
```

At least once, make sure to build the blackboard site-bundle. Once ready either use the menus available or hit `F5` to start the debug session for the extension. Before running the extension make sure you have a depi-server running and accessible.

#### Build Blackboard site-bundle

Go to `../blackboard-graph` to build the site-bundle for the blackboard graph.
(The `post_build` script will move over the site-bundle into the `./out`-directory.)

```
npm install && npm run build
```

#### Building vsix locally

Install `vsce` node_module globally (only needed once)

```
npm install --global @vscode/vsce
```

From root of this repository (depi-impl)

```
./install-and-build-vsix.sh
```

# Acknowledgements

This work was supported by the DARPA Assured Autonomy program and Air Force Research Laboratory. Any opinions, findings,
and conclusions or recommendations expressed in this material are those of the author(s) and do not necessarily reflect
the views of DARPA or AFRL.

#### Contact

caid-dev@vanderbilt.edu
