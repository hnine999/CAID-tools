# Depi-Blackboard

Graphical editor for displaying resources and relationships in the vscode extension.

## Dev-notes

Install dependencies:

```
npm install
```

To run as a standalone web-application using mocked data (see `src/depi-api`) run:

```
npm start
```

To build the bundle for the vscode extension run - this will copy over the bundle to `../vscode-depi` (see `post_build.js` for details).

```
npm run build
```

### Depi interface

```
[Blackboard ReactApp GUI]  <--vscode-webview-api-->  [vscode extension server]  <--grpc-->  [depi-server]
```
The interface with the vscode-extension (which in turn talks to the depi server) is implemented in `./src/depi-api/DepiApi.js` and the event-handler is in `./src/App.js`.

If adding any new requests/events - make sure to implement a mock method in `DepiApi.js` as well. Note that `./src/App.js` shouldn't have any logic for whether the actual api or mock is used.
