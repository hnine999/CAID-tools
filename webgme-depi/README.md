# WebGME Depi
- **vscode-webgme-depi** - Contains vscode extension for connecting webgme GUI with Depi server. 
- **webgme-depi-components** - Visualizer and api-client for communicating with depi via vscode. 

## Developers
#### Creating new vsix and docker image

1. Update to a new version (`x.x.x`) in `vscode-webgme-depi/package.json`, `webgme-depi-components/package.json`
2. `npm install` in `vscode-webgme-depi` and `webgme-depi-components`.
3. `git commit -am "Release x.x.x"`
4. `git push origin main`
5. `git tag vx.x.x`
6. `git push origin vx.x.x`

This will build a new vsix installer and a new docker image.


# Acknowledgements
This work was supported by the DARPA Assured Autonomy program and Air Force Research Laboratory. Any opinions, findings, 
and conclusions or recommendations expressed in this material are those of the author(s) and do not necessarily reflect 
the views of DARPA or AFRL.

#### Contact
caid-dev@vanderbilt.edu