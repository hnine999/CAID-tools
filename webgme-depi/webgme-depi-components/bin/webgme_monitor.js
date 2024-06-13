
const Express = require('express');
const bodyParser = require('body-parser');
const webgme = require('webgme');
const { depiUtils } = require('depi-node-client');
const gmeConfig = webgme.getGmeConfig();
const { getRootHash } = webgme.requirejs('common/storage/util');
const getResourceChanges = require('./getResourceChanges');
const logger = webgme.Logger.create('webgme-depi-monitor', gmeConfig.bin.log, false);

const CONFIG_KEY = 'depi';
config = gmeConfig.webhooks.defaults[CONFIG_KEY].options;

console.log('config (from webgme config/)\n', JSON.stringify(config, null, 2));


const app = new Express();
app.use(bodyParser.json());

const requestQueue = [];
let working = false;
async function processNextRequest() {
    if (working || requestQueue.length === 0) {
        return;
    }

    working = true;
    const request = requestQueue.shift();
    request.attempts += 1;
    let timeout = 0;

    try {
        await handleRequest(request.payload);
    } catch (err) {
        logger.error('Failed to handle request', err.message, err.stack);
        if (request.attempts >= config.maxAttempts) {
            logger.error('Reached maxAttempt', config.maxAttempts);
        } else {
            timeout = 2 ^ request.attempts * 5000;
            logger.info('Attempt number', request.attempts, 'will try again in', timeout / 1000, '[s]');
            requestQueue.unshift(request);
        }
    }

    working = false;
    setTimeout(processNextRequest, timeout);
}

async function handleRequest(payload) {
    // https://github.com/webgme/webgme/wiki/GME-WebHooks
    const { event, projectId } = payload;
    let newVersion = null;
    if (event === 'BRANCH_HASH_UPDATED') {
        newVersion = payload.data.newHash;
    } else if (event === 'TAG_CREATED') {
        newVersion = payload.data.tagName;
    } else {
        logger.warn('Unsupported event', event, 'only "BRANCH_HASH_UPDATED" supported TODO:');
        return;
    }

    const [userName, password] = config.depi.token.split(':'); // TODO: Actual token.
    const depiSession = await depiUtils.logInDepiClient(config.depi.url, userName, password);

    const { userId } = payload.data;

    const rgUrl = `?project=${projectId}`;

    logger.info('Resolved resourceGroupUrl for incoming request:', rgUrl);

    let resourceGroup;
    const resourceGroups = await depiUtils.getResourceGroups(depiSession);
    for (const rg of resourceGroups) {
        if (rg.toolId === config.toolId && rg.url.endsWith(rgUrl)) {
            resourceGroup = rg;
            break;
        }
    }

    if (!resourceGroup) {
        logger.info('No matching resource-group in depi', resourceGroups.map(rg => rg.url).join(', '));
        return;
    }

    const resources = await depiUtils.getResources(depiSession, [{
        toolId: config.toolId,
        resourceGroupName: resourceGroup.name,
        resourceGroupUrl: resourceGroup.url,
        urlPattern: '.*'
    }]);

    let changes = []
    if (resources.length === 0) {
        logger.info('No resources in resource group', resourceGroup.url);
    } else {
        changes = await getModelChanges(userId, projectId, resources, resourceGroup.version, newVersion, false);
        logger.info('There were', changes.length, 'update(s) in', resourceGroup.url);
        changes.forEach(c => logger.info(JSON.stringify(c)));
    }

    const {toolId, name, url} = resourceGroup;
    await depiUtils.updateResourceGroup(depiSession, toolId, name, url, newVersion, changes);
}

async function getModelChanges(userId, projectId, resources, oldVersion, newVersion, areTags) {
    let gmeAuth;
    let storage;
    let project;

    try {
        gmeAuth = await webgme.getGmeAuth(gmeConfig);
        // TODO: Consider caching the last opened project.
        storage = webgme.getStorage(logger, gmeConfig, gmeAuth);
        await storage.openDatabase();
        project = await storage.openProject({ projectId, username: userId });
        const oldRootHash = await getRootHash(project, areTags ? { tagName: oldVersion } : { commitHash: oldVersion });
        const newRootHash = await getRootHash(project, areTags ? { tagName: newVersion } : { commitHash: newVersion });
        const core = new webgme.Core(project, { globConf: gmeConfig, logger: logger.fork('core') });
        const oldRoot = await core.loadRoot(oldRootHash);
        const newRoot = await core.loadRoot(newRootHash);
        const res = await getResourceChanges(resources, core, oldRoot, newRoot);
        return res;
    } finally {
        storage && await storage.closeDatabase();
        gmeAuth && await gmeAuth.unload();
    }
}

app.post(config.path, async (req, res) => {
    const payload = req.body;

    logger.info('received payload', JSON.stringify(payload));
    requestQueue.push({ payload, attempts: 0 });
    processNextRequest();

    res.sendStatus(200);
});

const server = app.listen(config.port);

logger.info('Server listening for POST at', `http://127.0.0.1:${config.port}${config.path}`);

process.on('SIGINT', function () {
    server.close();
});