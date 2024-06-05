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

const depiHookConfig = {
    webgmeBaseUrl,
    "toolId": "webgme",
    "port": 9000,
    "path": '/webhook',
    "maxAttempts": 1,
    "depi": {
        "url": "depi-server:5150",
        "project": "TestProject",
        "token": "patrik:patrik"
    }
};

config.webhooks.defaults['depi'] = {
    description: 'Events generated for depi monitor',
    events: ['TAG_CREATED', 'BRANCH_HASH_UPDATED'],
    url: `http://webgme-monitor:${depiHookConfig.port}${depiHookConfig.path}`,
    options: depiHookConfig
};

validateConfig(config);
module.exports = config;
