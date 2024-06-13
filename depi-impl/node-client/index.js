const grpc = require('@grpc/grpc-js');
const depi = require('./src/pbs/depi_pb');
const { DepiClient } = require('./src/pbs/depi_grpc_pb');
const addAsyncMethods = require('./src/pbs/addAsyncMethods');
const depiUtils = require('./src/depiUtils');
let DepiExtensionApi;

let toExport = {
    grpc,
    depi,
    DepiClient,
    addAsyncMethods,
    depiUtils,
};

// Lazy load DepiExtensionApi since not every user of depi-node-client is a vscode extension and will have that as a dependency.
Object.defineProperties(toExport, {
    DepiExtensionApi: {
        get: function () {
            if (!DepiExtensionApi) {
                // Not sure why default needed here but not for depuUtils.
                DepiExtensionApi = require('./src/depiExtensionApi').default; 
            }

            return DepiExtensionApi;
        }
    },
});


module.exports = toExport;