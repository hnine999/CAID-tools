# WebGME-Depi
Wrapper around a [webgme](https://webgme.org) instance that uses components from webgme-depi-components for forwarding 
calls to a depi-server.

To edit the user settings JSON do `Ctrl/Cmd + Shift + P` and start typing Open User Settings (JSON). Invoke the command and
configure the webgme url server (note the trailing `/`).
```
    ...
    "webgme-depi.urls": ["http://<webgmehost-name>:<webgme-port>/"],
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