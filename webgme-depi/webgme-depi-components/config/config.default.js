'use strict';

var config = require('./config.webgme'),
    validateConfig = require('webgme/config/validator');

// URL webgme is availble at.
const webgmeBaseUrl = `http://127.0.0.1:${config.server.port}/`;

config.webhooks.enable = true;
config.plugin.webgmeBaseUrl = webgmeBaseUrl;
config.plugin.webgmePublicUrl = webgmeBaseUrl;
config.plugin.allowServerExecution = true;

const depiHookConfig = {
    "webgmeBaseUrl": webgmeBaseUrl,
    "toolId": "webgme",
    "port": 9000,
    "path": '/webhook',
    "maxAttempts": 1,
    "depi": {
        "url": "127.0.0.1:5150",
        "project": "TestProject",
        "token": "patrik:patrik"
    }
};

config.webhooks.defaults['depi'] = {
    description: 'Events generated for depi monitor',
    events: ['TAG_CREATED', 'BRANCH_HASH_UPDATED'],
    url: `http://127.0.0.1:${depiHookConfig.port}${depiHookConfig.path}`,
    options: depiHookConfig
};

validateConfig(config);
module.exports = config;
