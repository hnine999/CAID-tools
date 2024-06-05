const { depiUtils, depi } = require('../index');

const DEPI_URL = '127.0.0.1:5150';
const PROJECT = 'TestProject';
const USER_NAME = 'patrik';
const PASSWORD = 'patrik';


async function main() {
    const depiSession = await depiUtils.logInDepiClient(DEPI_URL, PROJECT, USER_NAME, PASSWORD);

    console.log(await depiUtils.getResourceGroups(depiSession));
    
    const pattern = new depi.ResourceRefPattern();
    pattern.setToolid('git');
    pattern.setResourcegroupurl('/extra3/caid/dummy8');
    pattern.setUrlpattern('.*');

    const resourceRequest = new depi.GetResourcesRequest();
    resourceRequest.setSessionid(depiSession.sessionId);
    resourceRequest.setPatternsList([pattern]);

    const rr = await depiSession.client.getResourcesAsync(resourceRequest);
    console.log(rr.getResourcesList().length);
    const call = depiSession.client.getResourcesAsStream(resourceRequest);

    let cnt = 0;
    call.on('data', function(data) {
        console.log('data', JSON.stringify(data, null, 2));
        cnt += 1;
        console.log(cnt);
        console.log(data.getResource());
        const res = new depi.GetResourcesAsStreamResponse(data);
        console.log(res.getResource());
    });

    call.on('end', function() {
        console.log('end');
    });

    call.on('error', function(error) {
      console.error('error', error);
    });

    call.on('status', function(status) {
        // console.error('status', status);
    });
}

main();

