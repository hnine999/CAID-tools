import * as vscode from 'vscode';
import { depiUtils, DepiSession } from 'depi-node-client';
import DepiExtensionApi from './depiExtensionApi';
/**
 * State wrt to depi integration.
 * One instance is created and kept alive as long as the panel is.
 * This instance is destroyed when the panel is and a new instance created whenever a new panel is brought up.
 */
export default class DepiState {
    log: Function;
    depiExtApi: DepiExtensionApi;
    depiWatcherId: string | null;
    pingIntervalId: NodeJS.Timeout | null;

    constructor(log: Function) {
        this.log = log;
        this.depiExtApi = new DepiExtensionApi(log);
        this.depiWatcherId = null;
        this.pingIntervalId = null;
    }

    async getDepiSession() {
        return await this.depiExtApi.getDepiSession();
    }

    async switchBranch(branchName: string) {
        const depiSession = await this.depiExtApi.getDepiSession();
        this.log('Branch switch from', depiSession.branchName, 'to', branchName);

        const currentBranch = await depiUtils.setBranch(depiSession, branchName);

        if (!currentBranch) {
            throw new Error(`Branch did not exist in depi [${branchName}]`);
        }

        depiSession.branchName = branchName;
    }

    async addDepiWatcher(onUpdate: Function) {
        const depiSession = await this.depiExtApi.getDepiSession();
        this.depiWatcherId = await depiUtils.watchDepi(depiSession, () => { onUpdate() }, (err) => { this.log(err) });

        const config = vscode.workspace.getConfiguration('webgme-depi');
        const depiServerPingIntervalSeconds = config.get<number>('depiserver_ping_interval_seconds')!;

        this.pingIntervalId = setInterval(async () => {
            this.log(
                'Pinging depi to keep session alive, will ping again in',
                depiServerPingIntervalSeconds,
                'seconds.'
            );
            try {
                await depiUtils.ping(depiSession as DepiSession);
            } catch (err) {
                this.log(err);
            }
        }, depiServerPingIntervalSeconds * 1000);
    }

    async destroy() {
        this.log('destroy invoked..');
        if (this.depiWatcherId) {
            this.log('clearing depiWatcher with id', this.depiWatcherId);
            const depiSession = await this.depiExtApi.getDepiSession();
            await depiUtils.unwatchDepi(depiSession, this.depiWatcherId);
            this.depiWatcherId = null;
        } else {
            this.log('.. no current watcher');
        }

        if (this.pingIntervalId) {
            this.log('clearing interval.');
            clearInterval(this.pingIntervalId);
            this.pingIntervalId = null;
        } else {
            this.log('.. no current ping interval.');
        }

        await this.depiExtApi.destroy();
    }
}