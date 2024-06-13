# WebGME-Client
Wrapper around a [webgme](https://webgme.org) instance. The main use-case for this extension is to provide an interface to [depi](https://github.com/vu-isis/CAID-tools) and communicate with the [Depi Browser](vscode:extension/vu-isis.depi). For that to work the configured GUI at webgme instance needs to use the components from [webgme-depi-components](../webgme-depi-components/README.md).

By default the depi integration is disabled, you can see the settings section below how to turn it on. Aside from the depi use-case this extension is a good starting point for anyone wanting to integrate webgme with vscode.

## Settings
To edit the user settings JSON do `Ctrl/Cmd + Shift + P` and start typing Open User Settings (JSON). Invoke the command and
configure the webgme url server (note the trailing `/`).
```
    ...
    "webgme-depi.urls": ["http://<webgmehost-name>:<webgme-port>/"],
    "webgme-depi.enableDepi": true
    ...
```

To start the editor do: `Ctrl/Cmd + Shift + P` and start typing `WebGME: Modeling Editor` and click or hit enter. This
should bring up the webgme instance.

# Acknowledgements
This work was supported by the DARPA Assured Autonomy program and Air Force Research Laboratory. Any opinions, findings, 
and conclusions or recommendations expressed in this material are those of the author(s) and do not necessarily reflect 
the views of DARPA or AFRL.

#### Contact
caid-dev@vanderbilt.edu