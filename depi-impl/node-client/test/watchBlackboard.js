const { depiUtils, depi } = require('../index');

const DEPI_URL = '127.0.0.1:5150';
const PROJECT = 'TestProject';
const USER_NAME = 'patrik';
const PASSWORD = 'patrik';


async function main() {
    const depiSession = await depiUtils.logInDepiClient(DEPI_URL, PROJECT, USER_NAME, PASSWORD);

    const watchRequest = new depi.WatchBlackboardRequest();
    watchRequest.setSessionid(depiSession.sessionId);

    const call = depiSession.client.watchBlackboard(watchRequest);

    call.on('data', function(data) {
        console.log('data', JSON.stringify(data, null, 2));
    });
    call.on('end', function() {
        console.log('end');
    });
    call.on('error', function(error) {
      console.error('error', error);
    });
    call.on('status', function(status) {
        console.error('status', status);
    });


    setTimeout(async () => {
        const unwatchRequest = new depi.UnwatchBlackboardRequest();
        unwatchRequest.setSessionid(depiSession.sessionId);
    
        const res = await depiSession.client.unwatchBlackboardAsync(unwatchRequest);

        if (!res.getOk()) {
            console.error('unwatch failed', res.getMsg());
        }

        call.cancel();
    }, 5000);
}

main();

