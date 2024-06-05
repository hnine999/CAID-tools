const { depiUtils, depi } = require('../index');
const { readFileSync } = require('node:fs');

const DEPI_URL = '129.59.107.74:5443';
const PROJECT = 'TestProject';
const USER_NAME = 'patrik';
const PASSWORD = 'patrik';


async function main() {

    const certPath = './test/cert.pem';

    const certContent = readFileSync(certPath).toString('utf8');
    console.log(certContent);

    const depiSession = await depiUtils.logInDepiClient(DEPI_URL, PROJECT, USER_NAME, PASSWORD, certContent,
         {'grpc.ssl_target_name_override': 'depi_server.isis.vanderbilt.edu'});

    const req = new depi.GetResourceGroupsRequest();
    req.setSessionid(depiSession.sessionId);

    let res = await depiSession.client.getResourceGroupsAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not getResourceGroupsAsync ' + res.getMsg());
    }

    console.log('Number of resource-groups #', res.getResourcegroupsList().length);
    res.getResourcegroupsList().forEach((rg) => console.log(rg.getUrl()));
}

main();

