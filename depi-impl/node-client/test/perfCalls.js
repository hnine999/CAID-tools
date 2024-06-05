const { depiUtils, depi } = require('../index');

const DEPI_URL = '127.0.0.1:5150';
const PROJECT = 'TestProject';
const USER_NAME = 'patrik';
const PASSWORD = 'patrik';


async function main() {
    const depiSession = await depiUtils.logInDepiClient(DEPI_URL, PROJECT, USER_NAME, PASSWORD);

    let t = Date.now();
    const resourceGroups = await depiUtils.getResourceGroups(depiSession);
    console.log(`Time: ${Math.round((Date.now() - t) / 100) / 10} [s]`);

    const patterns = resourceGroups.map((rg) => ({
        toolId: rg.toolId,
        resourceGroupName: rg.name,
        resourceGroupUrl: rg.url,
        // For resources
        urlPattern: '.*',
    }));

    for (const pattern of patterns) {
        let t = Date.now();
        const resources = await depiUtils.getResourcesStreamed(depiSession, [pattern]);
        console.log('Nbr of resources', resources.length);
        console.log(`Time: ${Math.round((Date.now() - t) / 100) / 10} [s]`);
    }

    t = Date.now();
    const links = await depiUtils.getAllLinksStreamed(depiSession);

    console.log('Nbr of links', links.length);

    console.log(`Time: ${Math.round((Date.now() - t) / 100) / 10} [s]`);
}

main();

