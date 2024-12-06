'use strict';

const config = require('./config.default');
const validateConfig = require('webgme/config/validator');

const mongoHost = process.env.MONGO_HOST || 'mongo';
const mongoPort = process.env.MONGO_PORT || 27017;

config.mongo.uri = `mongodb://${mongoHost}:${mongoPort}/webgme`;
// URL webgme is availble at.

const webgmeHost = process.env.GME_HOST || 'webgme';
const webgmePublicHost = process.env.GME_PUBLIC_HOST || 'localhost';
config.server.port = process.env.GME_PORT || 8888;

const webgmeBaseUrl = `http://${webgmeHost}:${config.server.port}/`;
const webgmePublicUrl = process.env.GME_PUBLIC_URL || `http://${webgmePublicHost}:${config.server.port}/`;

config.webhooks.enable = true;
config.plugin.webgmeBaseUrl = webgmeBaseUrl;
config.plugin.webgmePublicUrl = webgmePublicUrl;
config.plugin.allowServerExecution = true;

const depiHost = process.env.DEPI_HOST || 'depi-server';
const depiPort = process.env.DEPI_PORT || '5150';
const hookHost = process.env.DEPI_HOOK_HOST || 'webgme-monitor';
const hookPort = process.env.DEPI_HOOK_PORT || '9000';


const depiHookConfig = {
    webgmeBaseUrl,
    "toolId": "webgme",
    "port": hookPort,
    "path": '/webhook',
    "maxAttempts": 1,
    "depi": {
        "url": `${depiHost}:${depiPort}`,
        "project": "TestProject",
        "token": "patrik:patrik"
    }
};

config.webhooks.defaults['depi'] = {
    description: 'Events generated for depi monitor',
    events: ['TAG_CREATED', 'BRANCH_HASH_UPDATED'],
    url: `http://${hookHost}:${hookPort}${depiHookConfig.path}`,
    options: depiHookConfig
};

validateConfig(config);
module.exports = config;
