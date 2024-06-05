import * as vscode from 'vscode';
import { API as GitAPI } from './@types/git';
import { depiUtils, DepiSession, Resource } from 'depi-node-client';
import { getGraphEventHandler, setWebviewContent, getGraphDistUris } from './blackboardGraphUtils';
import {
    getGitApi,
    getGitResourceFromUri,
    revealGitResource,
    viewGitResourceDiff,
    parseResourceGroupUrl,
    tryResolveResourceGroupUrl,
} from './gitUtils';
import DepiUiModel from './DepiUIModel';

const TOKEN_STORE_KEY = 'DEPI_AUTH_TOKEN';
const NBR_OF_LOGIN_ATTEMPTS = 5;
let channel: vscode.OutputChannel;
let git: GitAPI;

let depiSession: DepiSession | null;
let pingIntervalId: NodeJS.Timer | null;
let serverUnreachable: boolean = false;

let panel: vscode.WebviewPanel | null;
let uiModel: DepiUiModel | null;
let toDispose: vscode.Disposable[] = [];
let createNewSessionCmd: (...args: any[]) => any;
let manuallyDisposing = false;

async function disposeOfState() {
    panel?.dispose();
    panel = null;
    toDispose.forEach((d) => d.dispose());
    toDispose = [];
    await uiModel?.dispose();
    uiModel = null;
}

function log(...messages: any[]) {
    if (!channel) {
        throw new Error('Channel not initialized');
    }

    const currentDate = new Date();
    const milliseconds = currentDate.getMilliseconds();
    const formattedMilliseconds = String(milliseconds).padStart(3, '0');

    const timestamp = currentDate.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
    });

    channel.appendLine(`${timestamp}.${formattedMilliseconds} - ${messages.join(' ')}`);
}

async function loginDepi(context: vscode.ExtensionContext, forceNewSession: boolean = false) {
    if (depiSession && !forceNewSession) {
        return;
    }

    let configuration = vscode.workspace.getConfiguration('depi');
    const url = configuration.get<string>('url')!;
    const userName = configuration.get<string>('user_name')!;
    const sslCertPath = configuration.get<string>('ssl_cert_path')!;
    const sslTargetNameOverride = configuration.get<string>('ssl_target_name_override')!;
    const depiServerPingIntervalSeconds = configuration.get<number>('depiserver_ping_interval_seconds')!;
    const options: any = {};

    if (sslTargetNameOverride) {
        options['grpc.ssl_target_name_override'] = sslTargetNameOverride;
    }

    let certificate = '';
    if (sslCertPath) {
        const readData = await vscode.workspace.fs.readFile(vscode.Uri.file(sslCertPath));
        certificate = Buffer.from(readData).toString('utf8');
    }

    depiSession = null;
    // 1. First try to log in using the token
    const token = await context.secrets.get(TOKEN_STORE_KEY);
    if (token) {
        try {
            depiSession = await depiUtils.logInDepiClientWithToken(url, token, certificate, options);
            await context.secrets.store(TOKEN_STORE_KEY, depiSession.token);
        } catch (err: any) {
            log(err);
            if (err.code === 14) {
                vscode.window.showErrorMessage(`Can not reach "${url}"`);
                return;
            }

            if (err.message.includes('Token expired') || err.message.includes('Invalid token')) {
                vscode.window.showErrorMessage(`${err.message} - login with credentials.`);
            }
        }
    }

    // 2. If token expired or it didn't work for any other reason - try logging in with password.
    if (!depiSession) {
        let password: string | undefined;
        for (var i = 1; i <= NBR_OF_LOGIN_ATTEMPTS && !password; i++) {
            const passwordTry = await vscode.window.showInputBox({
                ignoreFocusOut: true,
                title: 'Depi Login',
                prompt: `Enter password for user ${userName}. Attempt ${i} out of ${NBR_OF_LOGIN_ATTEMPTS}.`,
                password: true,
            });

            if (passwordTry) {
                try {
                    log('Calling out to log in at', url);
                    depiSession = await depiUtils.logInDepiClient(url, userName, passwordTry, certificate, options);
                    await context.secrets.store(TOKEN_STORE_KEY, depiSession.token);
                    password = passwordTry;
                } catch (err: any) {
                    log(err);
                    if (err.code === 14) {
                        vscode.window.showErrorMessage(`Can not reach "${url}"`);
                        return;
                    }
                }
            }
        }
    }

    if (!depiSession) {
        return;
    }

    pingIntervalId = setInterval(async () => {
        log('Pinging server to keep session alive, will ping again in', depiServerPingIntervalSeconds, 'seconds.');
        try {
            const pingResult = await depiUtils.ping(depiSession as DepiSession);
            await context.secrets.store(TOKEN_STORE_KEY, pingResult.token);
            if (serverUnreachable) {
                vscode.window.showInformationMessage('Connection to server re-established.');
                serverUnreachable = false;
                await createNewSessionCmd();
            }
        } catch (err: any) {
            log(err);
            vscode.window.showErrorMessage((err as Error).message);
            if (err.code !== 14) {
                serverUnreachable = false;
                // Probably an invalid session at this point.
                await createNewSessionCmd();
            } else {
                serverUnreachable = true;
            }
        }
    }, depiServerPingIntervalSeconds * 1000);

    vscode.window.showInformationMessage(`Connection to depi-server at ${url} established.`);

    return { userName: depiSession.user, token, url, certificate, options };
}

export async function activate(context: vscode.ExtensionContext) {
    channel = vscode.window.createOutputChannel('depi');
    channel.show(); // TODO: Remove this at some point.

    log('Depi is being activated..');

    const userInfo = await loginDepi(context);

    if (!depiSession) {
        vscode.window.showErrorMessage('Could not establish depi connection!');
        throw new Error('Could not establish depi connection!');
    }

    try {
        git = await getGitApi();
    } catch (err) {
        log(err);
        vscode.window.showErrorMessage((err as Error).message);
    }

    const distUris = await getGraphDistUris(context.extensionUri);

    async function displayBlackboardPanel(resource?: Resource, branchName?: string, dependants?: boolean) {
        log('displayBlackboardPanel, showDependencyGraph?', Boolean(resource), 'branchName=', branchName);
        if (panel) {
            log('Panel instance already available - will dispose of it');
            manuallyDisposing = true;
            await disposeOfState();
        }

        uiModel = new DepiUiModel(depiSession as DepiSession, log);

        log('Creating new panel - registering new event-listeners..');
        panel = vscode.window.createWebviewPanel('graph', 'Depi', vscode.ViewColumn.Two, {
            retainContextWhenHidden: true,
            enableScripts: true,
        });

        toDispose.push(
            panel.webview.onDidReceiveMessage(
                getGraphEventHandler(panel, uiModel, revealDepiResourceCmd, viewResourceDiffCmd, log)
            )
        );

        panel.onDidDispose(
            async () => {
                log('panel.onDidDispose..');
                if (manuallyDisposing) {
                    log('Panel is being manually disposed, will not dispose -> setting flag to false.');
                    manuallyDisposing = false;
                } else {
                    log('Panel tab was closed - disposing.');
                    await disposeOfState();
                }
            },
            undefined,
            context.subscriptions
        );

        setWebviewContent(
            panel,
            distUris.jsBundleUri,
            distUris.cssBundleUri,
            {},
            false,
            resource,
            dependants,
            branchName
        );
    }

    // Extension commands
    // Internally used by depi-extension
    createNewSessionCmd = async function createNewSessionCmd() {
        if (panel) {
            await panel.dispose();
            panel = null;
        }

        try {
            serverUnreachable = false;
            if (pingIntervalId) {
                clearInterval(pingIntervalId);
                pingIntervalId = null;
            }

            if (uiModel) {
                await uiModel.dispose();
                uiModel = null;
            }

            if (depiSession) {
                await depiUtils.logOut(depiSession);
                depiSession = null;
            }
        } catch (err) {
            const errMessage = (err as Error).message;
            if (errMessage.startsWith('Invalid session') || (err as Error).message) {
                uiModel = null;
                depiSession = null;
            } else {
                vscode.window.showErrorMessage('Could not clean-up previous state.');
                return;
            }
        }

        await loginDepi(context, true);

        if (!depiSession) {
            vscode.window.showErrorMessage('Could not establish a new depi connection!');
        } else {
            vscode.window.showInformationMessage('New depi session established - depi ready to use again!');
        }
    };

    async function addGitResourceToBlackboardCmd(uri: vscode.Uri) {
        try {
            log('addGitResourceToBlackboardCmd', uri);
            const resource = await getGitResourceFromUri(git, uri);
            const gitUrls = (await depiUtils.getResourceGroups(depiSession as DepiSession))
                .filter((rg) => rg.toolId === 'git')
                .map((rg) => rg.url);

            resource.resourceGroupUrl =
                tryResolveResourceGroupUrl(resource.resourceGroupUrl, gitUrls, log) || resource.resourceGroupUrl;

            const selectedOption = await vscode.window.showInformationMessage(
                'Would you like to select an existing resource in Depi as a dependency of this file?',
                { modal: true },
                'Yes',
                'No - just add the file to the blackboard.'
            );

            await depiUtils.addResourcesToBlackboard(depiSession as DepiSession, [resource]);

            if (selectedOption === 'Yes') {
                const targetResource = await selectDepiResourceCmd();
                if (targetResource) {
                    await depiUtils.addResourcesToBlackboard(depiSession as DepiSession, [targetResource]);
                    await depiUtils.addLinkToBlackboard(depiSession as DepiSession, resource, targetResource);
                }
            }

            if (!panel) {
                // FIXME: What if the dependency-graph is displayed?
                showBlackboardCmd();
            }
        } catch (err) {
            log(err);
            vscode.window.showErrorMessage((err as Error).message);
        }
    }

    async function showDependencyGraphForGit(uri: vscode.Uri, dependants?: boolean) {
        try {
            log('showDependencyGraphForGitResourceCmd', uri);
            const resource = await getGitResourceFromUri(git, uri);
            const gitUrls = (await depiUtils.getResourceGroups(depiSession as DepiSession))
                .filter((rg) => rg.toolId === 'git')
                .map((rg) => rg.url);

            resource.resourceGroupUrl =
                tryResolveResourceGroupUrl(resource.resourceGroupUrl, gitUrls, log) || resource.resourceGroupUrl;

            const pattern = {
                toolId: resource.toolId,
                resourceGroupName: resource.resourceGroupName,
                resourceGroupUrl: resource.resourceGroupUrl,
                urlPattern: `^${resource.url}$`,
            };

            log('pattern', JSON.stringify(pattern));

            const resources = await depiUtils.getResources(depiSession as DepiSession, [pattern]);

            log('resources', JSON.stringify(resources));

            if (resources.length === 0) {
                vscode.window.showErrorMessage('Resource is not in depi');
                return;
            }

            displayBlackboardPanel(resource, depiSession?.branchName, dependants);
        } catch (err) {
            log(err);
            vscode.window.showErrorMessage((err as Error).message);
        }
    }

    // Externally callable
    async function showBlackboardCmd(branchName?: string) {
        displayBlackboardPanel(undefined, branchName);
    }

    async function showDependencyGraphCmd(resource: Resource, branchName?: string) {
        displayBlackboardPanel(resource, branchName);
    }

    async function showDependantsGraphCmd(resource: Resource, branchName?: string) {
        displayBlackboardPanel(resource, branchName, true);
    }

    async function getDepiTokenCmd() {
        return { ...userInfo, token: await context.secrets.get(TOKEN_STORE_KEY) };
    }

    async function revealDepiResourceCmd(resource: Resource, branchName?: string) {
        const { toolId } = resource;

        log('revealDepiResourceCmd', branchName, JSON.stringify(resource));

        if (toolId === 'git') {
            try {
                log('Was git resource - using built-in method..');
                let configuration = vscode.workspace.getConfiguration('depi');
                const gitPlatform = configuration.get<string>('git_collaboration_platform')!;
                await revealGitResource(git, gitPlatform, resource, log);
            } catch (err) {
                log(err);
                vscode.window.showErrorMessage((err as Error).message);
            }
        } else {
            const allExtensions: readonly vscode.Extension<any>[] = vscode.extensions.all;
            const toolExtension = allExtensions.find(
                (extInfo) =>
                    extInfo.packageJSON.depi &&
                    extInfo.packageJSON.depi.toolId === toolId &&
                    typeof extInfo.packageJSON.depi.revealCmd === 'string'
            );

            if (!toolExtension) {
                vscode.window.showErrorMessage(`Could not find extension for "${toolId}" to reveal resource.`);
                return;
            }

            log(`Found external extension for ${toolId}..`);
            if (!toolExtension.isActive) {
                log('Extension was not activated - activating now ..');
                await toolExtension.activate();
            }

            await vscode.commands.executeCommand(toolExtension.packageJSON.depi.revealCmd, resource, branchName);
        }
    }

    async function viewResourceDiffCmd(resource: Resource, lastCleanVersion: string, branchName?: string) {
        const { toolId } = resource;

        log(
            'viewResourceDiffCmd',
            JSON.stringify(resource),
            'lastCleanVersion',
            lastCleanVersion,
            'branchName',
            branchName
        );

        if (toolId === 'git') {
            try {
                log('Was git resource - using built-in method..');
                let configuration = vscode.workspace.getConfiguration('depi');
                const gitPlatform = configuration.get<string>('git_collaboration_platform')!;
                if (gitPlatform === 'other') {
                    vscode.window.showErrorMessage('Cannot view diff fro resource using unknown git-platform.');
                    return;
                }

                await viewGitResourceDiff(gitPlatform, resource, lastCleanVersion, log);
            } catch (err) {
                log(err);
                vscode.window.showErrorMessage((err as Error).message);
            }
        } else {
            const allExtensions: readonly vscode.Extension<any>[] = vscode.extensions.all;
            const toolExtension = allExtensions.find(
                (extInfo) =>
                    extInfo.packageJSON.depi &&
                    extInfo.packageJSON.depi.toolId === toolId &&
                    typeof extInfo.packageJSON.depi.viewDiffCmd === 'string'
            );

            if (!toolExtension) {
                vscode.window.showErrorMessage(`Could not find extension for "${toolId}" to view diff for resource.`);
                return;
            }

            log(`Found external extension for ${toolId}..`);
            if (!toolExtension.isActive) {
                log('Extension was not activated - activating now ..');
                await toolExtension.activate();
            }

            await vscode.commands.executeCommand(
                toolExtension.packageJSON.depi.revealCmd,
                resource,
                lastCleanVersion,
                branchName
            );
        }
    }

    async function selectDepiResourceCmd(): Promise<Resource | null> {
        const resourceGroups = await depiUtils.getResourceGroups(depiSession as DepiSession);
        if (resourceGroups.length === 0) {
            vscode.window.showInformationMessage('No resource-groups available');
            return null;
        }

        const items = resourceGroups.map((rg) => ({ description: rg.url, label: rg.name, resourceGroup: rg }));
        const selectedRg = await vscode.window.showQuickPick(items, { placeHolder: 'Select resource-group' });

        if (!selectedRg) {
            return null;
        }

        const { resourceGroup } = selectedRg;
        const resources = await depiUtils.getResources(depiSession as DepiSession, [
            {
                toolId: resourceGroup.toolId,
                resourceGroupUrl: resourceGroup.url,
                urlPattern: '.*',
            },
        ]);

        if (resources.length === 0) {
            vscode.window.showInformationMessage('No resources in resource-group ' + resourceGroup.name);
            return null;
        }

        const rItems = resources.map((resource) => ({ description: resource.url, label: resource.name, resource }));
        const selectedResource = await vscode.window.showQuickPick(rItems, {
            placeHolder: `Select resource from ${resourceGroup.name}`,
        });

        if (!selectedResource) {
            return null;
        }

        log(JSON.stringify(selectedResource.resource));

        return selectedResource.resource;
    }

    // Externally callable commands
    context.subscriptions.push(vscode.commands.registerCommand('depi.showBlackboard', showBlackboardCmd));
    context.subscriptions.push(vscode.commands.registerCommand('depi.getDepiToken', getDepiTokenCmd));
    context.subscriptions.push(vscode.commands.registerCommand('depi.showDependencyGraph', showDependencyGraphCmd));
    context.subscriptions.push(vscode.commands.registerCommand('depi.showDependantsGraph', showDependantsGraphCmd));
    context.subscriptions.push(vscode.commands.registerCommand('depi.revealDepiResource', revealDepiResourceCmd));
    context.subscriptions.push(vscode.commands.registerCommand('depi.viewResourceDiff', viewResourceDiffCmd));
    context.subscriptions.push(vscode.commands.registerCommand('depi.selectDepiResource', selectDepiResourceCmd));
    context.subscriptions.push(vscode.commands.registerCommand('depi.createNewSession', createNewSessionCmd));
    // Internal commands
    context.subscriptions.push(
        vscode.commands.registerCommand('depi.addGitResourceToBlackboard', addGitResourceToBlackboardCmd)
    );
    context.subscriptions.push(
        vscode.commands.registerCommand('depi.showDependencyGraphForGitResource', (uri: vscode.Uri) => {
            return showDependencyGraphForGit(uri, false);
        })
    );
    context.subscriptions.push(
        vscode.commands.registerCommand('depi.showDependantsGraphForGitResource', (uri: vscode.Uri) => {
            return showDependencyGraphForGit(uri, true);
        })
    );

    log('Activation done!');
}

// This method is called when your extension is deactivated
export async function deactivate() {
    log('deactivated');
    if (pingIntervalId) {
        clearInterval(pingIntervalId);
    }

    if (panel) {
        panel.dispose();
        panel = null;
    }

    if (uiModel) {
        await uiModel.dispose();
        uiModel = null;
    }

    if (depiSession) {
        await depiUtils.logOut(depiSession);
        depiSession = null;
    }
}
