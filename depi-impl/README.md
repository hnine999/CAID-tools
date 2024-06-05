# Depi

- **blackboard-graph** - GUI for depi (used in vscode-depi)
- **depi** - depi-server implmented in go and git monitors implmented in python
- **node-client** - depi client in ts/js
- **vscode-depi** - vscode extension for depi GUI with built-in support for handling git resources (uses the blackboard-graph and node-client)

## Developers
#### Creating new vsix and docker images

TODO: Update with instructions for GO

1. Update to a new version (`x.x.x`) in `vscode-depi/package.json`, `depi/client/pyproject.toml`, and `depi/monitors/pyproject.toml`
2. `git commit -am "Release x.x.x"`
3. `git push origin main`
4. `git tag vx.x.x`
5. `git push origin vx.x.x`

This will build a new vsix installer and new docker images.


# Acknowledgements
This work was supported by the DARPA Assured Autonomy program and Air Force Research Laboratory. Any opinions, findings, 
and conclusions or recommendations expressed in this material are those of the author(s) and do not necessarily reflect 
the views of DARPA or AFRL.

#### Contact
caid-dev@vanderbilt.edu