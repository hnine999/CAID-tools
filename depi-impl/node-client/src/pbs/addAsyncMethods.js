const util = require('util');

/**
 * Add async-methods returning promises.
 * @param {DepiClient} client - Instance of depi-client 
 */
function addAsyncMethods(client) {
    Object.keys(client.__proto__).forEach((key) => {
        // Only convert functions that perform unary calls - streams don't need async methods.
        if (typeof client[key] === 'function' && !client[key].responseStream && !client[key].requestStream) {
            client[`${key}Async`] = util.promisify(client[key]);
        }
    });
}

module.exports = { addAsyncMethods };