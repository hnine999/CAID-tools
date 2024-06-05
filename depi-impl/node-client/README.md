# DEPI NodeJS Client

This is published [as depi-node-client at npmjs](https://www.npmjs.com/package/depi-node-client) and contains the classes (plus functions at a higher level of abstraction) for the gRPC [protocol buffers for depi.](../depi/proto/depi.proto)

## Generating Classes and Resources from .proto

Install dependencies:

```sh
npm install

# Apple M1 users should install for x64 due to grpc-tools not supporting arm64
npm install --target_arch=x64
```

Use [proto compiler](https://www.npmjs.com/package/grpc-tools) and [`ts-protoc-gen`](https://www.npmjs.com/package/ts-protoc-gen) to generate the TypeScript files:

Important! This needs to be executed from the directory where this file is.

```sh
npm run build
```

To use the async API for the client. Including the following snippet when creating the depi-client instance.
These `*Async` methods are generate in the d.ts by `generateAsyncTypes.js` which is run as part of the build.

```javascript
const { DepiClient } = require('./pbs/depi_grpc_pb');
const addAsyncMethods = require('./pbs/addAsyncMethods');

const client = new DepiClient('127.0.0.1:5150', grpc.credentials.createInsecure());
addAsyncMethods(client);

// Example using the async/promise methods,
const req = new depi.LoginRequest();
const loginResponse = await client.loginAsync(req);
```

Note that the recommended way to communicate with depi is thru the utility methods in `src/depiUtils.ts`.

```typescript
import { depiUtils } from 'depi-node-client';

const depiSession = await depiUtils.logInDepiClient(url, userName, password, null, options);
const resourceGroups = await depiUtils.getResourceGroups(depiSession);

```

### Publish a Release

(Make sure to `npm run build` and check it's up-to-date). Also if adding a function in depi-utils - don't forget to add it to the default export!

1. `npm run compile`
1. Update to a new version (`x.x.x`) in `package.json`
1. `git commit -am "Node-client release x.x.x"`
1. `git push origin main`
1. `npm publish ./`