import * as vscode from 'vscode';
import CONSTANTS from './CONSTANTS';
import DepiExtensionApi from './depiExtensionApi';
import { Resource, ResourceRef, ResourcePattern, depiUtils } from 'depi-node-client';
import DepiState from './DepiState';

const { EVENTS } = CONSTANTS;

export async function getGraphEventHandler(panel: vscode.WebviewPanel, depiState: DepiState, branchName: string, log: Function) {
    const depiExtApi = new DepiExtensionApi(log);
    const eventJobQueue: any[] = [];
    let working = false;
    async function processNextJob() {
        if (working || eventJobQueue.length === 0) {
            return;
        }

        working = true;
        await processMessage(eventJobQueue.shift());
        working = false;
        setTimeout(processNextJob);
    }

    if (branchName !== 'main') {
        await depiState.switchBranch(branchName);
    }

    await depiState.addDepiWatcher(function onUpdate() {
        panel.webview.postMessage({ type: CONSTANTS.EVENTS.DEPI_UPDATED });
    });

    async function processMessage(message: any) {
        const { commandId, type, data } = message;
        try {
            log(`\nGot message from graph-editor: ${JSON.stringify(message)}`);
            switch (type) {
                case EVENTS.GET_BRANCH_NAME:
                    await panel.webview.postMessage({ commandId, result: branchName });
                    break;
                case EVENTS.GET_RESOURCE_INFO:
                    const rps: ResourcePattern[] = (data as ResourceRef[]).map(rr => ({
                        toolId: rr.toolId,
                        resourceGroupUrl: rr.resourceGroupUrl,
                        urlPattern: rr.url,
                    }));
                    const resources = await depiUtils.getResources(await depiState.getDepiSession(), rps);
                    await panel.webview.postMessage({ commandId, result: resources });
                    break;
                case EVENTS.SHOW_DEPENDENCY_GRAPH:
                    await depiExtApi.showDependencyGraph(data);
                    await panel.webview.postMessage({ commandId });
                    break;
                case EVENTS.SHOW_DEPENDANTS_GRAPH:
                    await depiExtApi.showDependantsGraph(data);
                    await panel.webview.postMessage({ commandId });
                    break;
                case EVENTS.SHOW_BLACKBOARD:
                    await depiExtApi.showBlackboard();
                    await panel.webview.postMessage({ commandId });
                    break;
                case EVENTS.REVEAL_RESOURCE:
                    await depiExtApi.revealDepiResource(data);
                    await panel.webview.postMessage({ commandId });
                    break;
                case EVENTS.GET_DEPENDENCY_GRAPH:
                    const dependencyGraph = await depiUtils.getDependencyGraph(await depiState.getDepiSession(), data);
                    await panel.webview.postMessage({ commandId, result: dependencyGraph });
                    break;
                case EVENTS.GET_DEPENDANTS_GRAPH:
                    const dependantsGraph = await depiUtils.getDependencyGraph(await depiState.getDepiSession(), data, true);
                    await panel.webview.postMessage({ commandId, result: dependantsGraph });
                    break;
                case EVENTS.GET_DEPENDENCIES:
                    const dependencies = await depiUtils.getDependencies(await depiState.getDepiSession(), data);
                    await panel.webview.postMessage({ commandId, result: dependencies });
                    break;
                case EVENTS.GET_DEPENDANTS:
                    const dependants = await depiUtils.getDependencies(await depiState.getDepiSession(), data, true);
                    await panel.webview.postMessage({ commandId, result: dependants });
                    break;
                // Edit calls
                case EVENTS.ADD_AS_RESOURCE:
                    await depiUtils.addResourcesToBlackboard(await depiState.getDepiSession(), [data]);
                    await depiExtApi.showBlackboard();
                    await panel.webview.postMessage({ commandId });
                    break;
                case EVENTS.REMOVE_AS_RESOURCE:
                    // TODO: Clean-up links??
                    await depiUtils.deleteEntriesFromDepi(await depiState.getDepiSession(), { links: [], resources: [data] });
                    await panel.webview.postMessage({ commandId });
                    break;
                case EVENTS.ADD_DEPENDANT:
                case EVENTS.ADD_DEPENDENCY:
                    const otherResource = await depiExtApi.selectDepiResource();
                    if (!otherResource) {
                        await panel.webview.postMessage({ commandId });
                    }

                    await depiUtils.addResourcesToBlackboard(await depiState.getDepiSession(), [data, otherResource]);
                    if (type === EVENTS.ADD_DEPENDENCY) {
                        await depiUtils.addLinkToBlackboard(await depiState.getDepiSession(), data, otherResource as Resource);
                    } else {
                        await depiUtils.addLinkToBlackboard(await depiState.getDepiSession(), otherResource as Resource, data);
                    }

                    await depiUtils.saveBlackboard(await depiState.getDepiSession());
                    await panel.webview.postMessage({ commandId });
                    break;
                case EVENTS.REMOVE_DEPENDENCY:
                case EVENTS.REMOVE_DEPENDANT:
                    await depiUtils.deleteEntriesFromDepi(await depiState.getDepiSession(), { resources: [], links: [data] });
                    break;
                default:
                    throw new Error('Unexpect message type "' + type + '"');
            }

        } catch (err) {
            log(err);
            await panel.webview.postMessage({
                commandId,
                error: (err as Error).message,
            });
        }
    }

    return function eventHandler(message: any) {
        eventJobQueue.push(message);
        processNextJob();
    };
}