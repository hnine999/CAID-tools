const grpc = require('@grpc/grpc-js');
const depi = require('./src/pbs/depi_pb');
const { DepiClient } = require('./src/pbs/depi_grpc_pb');
const addAsyncMethods = require('./src/pbs/addAsyncMethods');
const depiUtils = require('./src/depiUtils');

module.exports = {
    grpc,
    depi,
    DepiClient,
    addAsyncMethods,
    depiUtils
};