/*jshint node: true*/
/**
 * @author lattmann / https://github.com/lattmann
 */

var config = require('./config.default');

config.server.port = 9001;
config.mongo.uri = 'mongodb://127.0.0.1:27017/webgme_tests';

config.webhooks.defaults['depi'].options.webgmeBaseUrl = `http://127.0.0.1:${config.server.port}/`;

module.exports = config;
