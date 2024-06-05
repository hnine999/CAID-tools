import * as vscode from 'vscode';

import { depiUtils, Resource, ResourceGroupRef } from 'depi-node-client';
import { EVENT_TYPES } from './EVENT_TYPES';
import DepiUiModel from './DepiUIModel';

export async function getGraphDistUris(extensionUri: vscode.Uri) {
    const assetManifestUri = vscode.Uri.joinPath(extensionUri, 'out', 'asset-manifest.json');
    try {
        const readData = await vscode.workspace.fs.readFile(assetManifestUri);
        const manifest = JSON.parse(Buffer.from(readData).toString('utf8'));
        return {
            jsBundleUri: vscode.Uri.joinPath(extensionUri, 'out', manifest.files['main.js']),
            cssBundleUri: vscode.Uri.joinPath(extensionUri, 'out', manifest.files['main.css']),
        };
    } catch (err) {
        if ((err as vscode.FileSystemError).code === 'FileNotFound') {
            throw new Error('Could not find asset-manifest.json - did you run "npm build" from ../blackboard-graph?');
        }
        throw err;
    }
}

export function setWebviewContent(
    panel: vscode.WebviewPanel,
    jsBundleUri: vscode.Uri,
    cssBundleUri: vscode.Uri,
    userPreferences: object,
    isDarkTheme: boolean,
    resource?: Resource,
    dependants?: boolean,
    branchName?: string
) {
    panel.webview.html = `<!DOCTYPE html>
  <html lang="en">
  <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <link href="${panel.webview.asWebviewUri(cssBundleUri)}" rel="stylesheet">
      <title>GSN</title>
  </head>
  <body style="color: ${
      isDarkTheme ? '#fff' : '#212B36'
  }; padding: 0; font-family: "Roboto","Helvetica","Arial",sans-serif;">
    <div
        id="root"
        data-ts="${Date.now() /* Make sure it's unique so it doesn't keep any old model/state cached. */}"
        data-user-preferences='${JSON.stringify(userPreferences)}'
        data-start-resource='${resource ? JSON.stringify({ resource, dependants }) : ''}'
        data-branch-name='${branchName ? branchName : 'main'}'
        data-dark-mode="${isDarkTheme}"
    ></div>
    <script src="${panel.webview.asWebviewUri(jsBundleUri)}"></script>
  </body>
  </html>`;
}

export function getGraphEventHandler(
    panel: vscode.WebviewPanel,
    uiModel: DepiUiModel,
    revealDepiResource: Function,
    viewResourceDiff: Function,
    log: Function
) {
    const eventJobQueue: any[] = [];
    let working = false;
    let expandCounter = 0;

    async function processNextJob() {
        if (working || eventJobQueue.length === 0) {
            return;
        }

        working = true;
        await processMessage(eventJobQueue.shift());
        working = false;
        setTimeout(processNextJob);
    }

    async function sendError(err: Error) {
        await panel.webview.postMessage({
            type: EVENT_TYPES.ERROR_MESSAGE,
            value: err.message,
        });
    }

    async function sendDependencyGraph(resource: any, dependants?: boolean) {
        log('Requesting dependency graph', resource);
        const graphData = await depiUtils.getDependencyGraph(uiModel.depiSession, resource, dependants);
        log('dependencyGraphLinks count:', graphData.links.length);
        await panel.webview.postMessage({
            type: EVENT_TYPES.DEPENDENCY_GRAPH,
            value: { ...graphData, dependants },
        });
    }

    async function sendDepiModel(resourceGroups: ResourceGroupRef[], increaseExpand?: boolean) {
        log('Requesting depi model, resourceGroups:', ...resourceGroups.map(({ url }) => url));
        const depiModel = await depiUtils.getDepiModel(uiModel.depiSession, resourceGroups);
        if (increaseExpand) {
            expandCounter += 1;
        }

        log(
            '[depiModel] expandCounter',
            expandCounter,
            ' #res:',
            depiModel.resources.length,
            '#links:',
            depiModel.links.length
        );
        await panel.webview.postMessage({
            type: EVENT_TYPES.DEPI_MODEL,
            value: { ...depiModel, expandState: expandCounter },
        });
    }

    async function sendBlackboardModel() {
        log('Requesting blackboard model');
        const blackboardModel = await depiUtils.getBlackboardModel(uiModel.depiSession);
        log('[blackboard] #res', blackboardModel.resources.length, '#links', blackboardModel.links.length);
        await panel.webview.postMessage({
            type: EVENT_TYPES.BLACKBOARD_MODEL,
            value: blackboardModel,
        });
    }

    async function sendBranchesAndTags() {
        log('Requesting branches and tags');
        const branchesAndTags = await depiUtils.getBranchesAndTags(uiModel.depiSession);
        log('[branchesAndTags] #branches', branchesAndTags.branches.length, '#tags', branchesAndTags.tags.length);
        await panel.webview.postMessage({
            type: EVENT_TYPES.BRANCHES_AND_TAGS,
            value: branchesAndTags,
        });
    }

    async function processMessage(message: any) {
        const { type, value } = message;
        try {
            log(`\nGot message from graph-editor: ${JSON.stringify(message)}`);

            switch (type) {
                case EVENT_TYPES.REQUEST_BRANCHES_AND_TAGS:
                    await sendBranchesAndTags();
                    break;
                case EVENT_TYPES.REQUEST_DEPI_MODEL:
                    await uiModel.setStateToBlackboard(value.branchName, sendBlackboardModel, sendDepiModel, sendError);
                    await sendDepiModel(uiModel.activeResourceGroups as ResourceGroupRef[]);
                    break;
                case EVENT_TYPES.REQUEST_BLACKBOARD_MODEL:
                    await sendBlackboardModel();
                    break;
                case EVENT_TYPES.REQUEST_DEPENDENCY_GRAPH:
                    await uiModel.setStateToDependencyGraph(
                        value.resource,
                        value.branchName,
                        value.dependants,
                        sendDependencyGraph,
                        sendError
                    );
                    await sendDependencyGraph(value.resource, value.dependants);
                    break;
                case EVENT_TYPES.EXPAND_RESOURCE_GROUPS:
                    value.forEach((rgRef: ResourceGroupRef) => {
                        const isAlreadyActive = uiModel.activeResourceGroups?.some((rg) =>
                            depiUtils.isSameResourceGroup(rg, rgRef)
                        );

                        if (!isAlreadyActive) {
                            uiModel.activeResourceGroups?.push(rgRef);
                        }
                    });
                    await sendDepiModel(uiModel.activeResourceGroups as ResourceGroupRef[], true);
                    break;
                case EVENT_TYPES.COLLAPSE_RESOURCE_GROUPS:
                    uiModel.activeResourceGroups = (uiModel.activeResourceGroups || []).filter((rg) => {
                        const shouldBeCollapsed = value.some((rgRef: ResourceGroupRef) =>
                            depiUtils.isSameResourceGroup(rg, rgRef)
                        );

                        return !shouldBeCollapsed;
                    });
                    await sendDepiModel(uiModel.activeResourceGroups as ResourceGroupRef[]);
                    break;
                case EVENT_TYPES.LINK_RESOURCES:
                    await depiUtils.addLinkToBlackboard(uiModel.depiSession, value.source, value.target);
                    break;
                case EVENT_TYPES.EDIT_RESOURCE_GROUP:
                    if (value.remove) {
                        await depiUtils.removeResourceGroup(uiModel.depiSession, value.resourceGroupRef);
                    } else {
                        await depiUtils.editResourceGroupProperties(
                            uiModel.depiSession,
                            value.resourceGroupRef,
                            value.updateDesc.name,
                            value.updateDesc.toolId,
                            value.updateDesc.url,
                            value.updateDesc.version
                        );
                    }
                    break;
                case EVENT_TYPES.SAVE_BLACKBOARD:
                    try {
                        await depiUtils.saveBlackboard(uiModel.depiSession);
                        await depiUtils.clearBlackboard(uiModel.depiSession);
                        await sendDepiModel(uiModel.activeResourceGroups as ResourceGroupRef[]);
                    } catch (err: any) {
                        const errMsg = err.message as string;
                        if (
                            errMsg.includes('Resource version in blackboard') &&
                            errMsg.includes('does not match resource version in Depi')
                        ) {
                            vscode.window.showErrorMessage(errMsg);
                            vscode.window.showInformationMessage('Please clear the blackboard.');
                            return;
                        }

                        throw err;
                    }
                    break;
                case EVENT_TYPES.CLEAR_BLACKBOARD:
                    await depiUtils.clearBlackboard(uiModel.depiSession);
                    break;
                case EVENT_TYPES.REMOVE_ENTRIES_FROM_BLACKBOARD:
                    await depiUtils.removeEntriesFromBlackboard(uiModel.depiSession, value);
                    break;
                case EVENT_TYPES.DELETE_ENTRIES_FROM_DEPI:
                    await depiUtils.deleteEntriesFromDepi(uiModel.depiSession, value);
                    break;
                case EVENT_TYPES.REVEAL_IN_EDITOR:
                    revealDepiResource(value as Resource);
                    break;
                case EVENT_TYPES.VIEW_RESOURCE_DIFF:
                    viewResourceDiff(value.resource, value.lastCleanVersion);
                    break;
                case EVENT_TYPES.MARK_ALL_CLEAN:
                    await depiUtils.markAllClean(uiModel.depiSession, value.links, log);
                    break;
                case EVENT_TYPES.MARK_LINKS_CLEAN:
                    await depiUtils.markLinksClean(uiModel.depiSession, value.links, value.propagate);
                    break;
                case EVENT_TYPES.MARK_INFERRED_DIRTINESS_CLEAN:
                    await depiUtils.markInferredDirtinessClean(
                        uiModel.depiSession,
                        value.link,
                        value.dirtinessSource,
                        value.propagate
                    );
                    break;
                default:
                    const msg = `Unknown message type from webview: "${type}"`;
                    log(msg);
            }
        } catch (err) {
            log(err);
            sendError(err as Error);
        }
    }

    return function eventHandler(message: any) {
        eventJobQueue.push(message);
        processNextJob();
    };
}
