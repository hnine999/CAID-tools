import * as vscode from 'vscode';
import * as path from 'path';
import { Trace } from 'vscode-jsonrpc';
import { LanguageClient } from 'vscode-languageclient/node';
import { json2gsn } from 'json2gsn';
import { Resource } from 'depi-node-client';

import { API as GitAPI } from './@types/git';
import { initializeLanguageClient } from './languageClient';
import { readInModelHash, generateNewModel } from './util';
import CONSTANTS from './CONSTANTS';
import getGraphEventHandler, { checkAndSendModelToGraph, emitUndoRedoAvailable, postCommandToLSP } from './getGraphEventHandler';
import { ModelContext } from './@types/gsn';
import GsnDepi from './GsnDepi';
import { getGitApi, revealGitResourceInBrowser, tryFindGitRepoAtResourceGroupUrl, getRepoRoothPath } from './gitUtils';
import GsnReview from './GsnReview';


let lc: LanguageClient;
let ch: vscode.OutputChannel;
let panel: vscode.WebviewPanel;
let git: GitAPI;

function log(...messages: any[]) {
    if (!ch) {
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

    ch.appendLine(`${timestamp}.${formattedMilliseconds} - ${messages.join(' ')}`);
}
// This holds the state about which gsn model is being used.
const modelContext: ModelContext = {
    modelHash: null,
    dirUri: null,
    gsnDepi: null,
    gsnReview: null,
    undoStack: [],
    redoStack: [],
};

export async function activate(context: vscode.ExtensionContext) {
    ch = vscode.window.createOutputChannel('gsn-xtext');
    if (process.env.SEPARATE_SERVER) {
        // Only bring this up when debugging.
        ch.show();
    }

    log('Starting activation ...');
    lc = initializeLanguageClient(context);

    try {
        git = await getGitApi();
    } catch (err) {
        log(err);
        vscode.window.showErrorMessage((err as Error).message);
        return;
    }

    function getUserPreferences() {
        const config = vscode.workspace.getConfiguration('gsnGraph');

        return {
            enableDepi: config.get<boolean>('enableDepi', false),
            enforceUniqueNames: config.get<boolean>('enforceUniqueNames', false),
            lightMode: config.get<boolean>('lightMode', true),
            useShortGsnNames: config.get<boolean>('useShortGsnNames', true),
        };
    }

    function getGsnCommandHandler(lspCommand: string) {
        return async () => {
            let activeEditor = vscode.window.activeTextEditor;
            if (!activeEditor || !activeEditor.document || activeEditor.document.languageId !== 'gsn') {
                vscode.window.showErrorMessage(`GSN Command must be invoked from an active .gsn-document.`);
                return;
            }

            const modelDir = path.dirname(activeEditor.document.uri.path);

            if (modelHasDirtyFiles(modelDir)) {
                vscode.window.showInformationMessage(
                    `The .gsn-documents are not persisted - save files before running ${lspCommand}.`
                );
                return;
            }

            try {
                await postCommandToLSP(log, lspCommand, { modelDir });
                vscode.window.showInformationMessage(`Command succeeded ${lspCommand}`);
            } catch (err) {
                log(err);
                vscode.window.showErrorMessage((err as Error).message);
            }
        }
    }

    context.subscriptions.push(
        vscode.commands.registerCommand('gsn.assign-uuids', getGsnCommandHandler(CONSTANTS.LSP.ASSIGN_UUIDS_COMMAND))
    );
    context.subscriptions.push(
        vscode.commands.registerCommand('gsn.generate-model-json', getGsnCommandHandler(CONSTANTS.LSP.GENERATE_MODEL_JSON_COMMAND))
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('gsn.get-model-json', async (modelDir: string) => {
            if (typeof modelDir !== 'string') {
                throw new Error('gsn.get-model-json takes a model directory path as first argument!');
            }

            return await postCommandToLSP(log, CONSTANTS.LSP.GENERATE_MODEL_JSON_COMMAND, { modelDir });
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('gsn.model-json-to-gsn', (modelJson: any[]) => {
            return json2gsn(modelJson);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('gsn.generate-gsn-from-json', async (uri: vscode.Uri) => {
            try {
                const readData = await vscode.workspace.fs.readFile(uri);
                const modelJson = JSON.parse(Buffer.from(readData).toString('utf8'));
                const { errors, contents } = json2gsn(modelJson);

                if (errors && errors.length > 0) {
                    errors.forEach(e => log(JSON.stringify(e)));
                    throw new Error('Could not convert json to gsn - check output for details');
                }

                const res = await generateNewModel(uri, path.basename(uri.fsPath).split('.')[0], contents);

                vscode.window.showInformationMessage(`Created template model at ${res.path}`);
            } catch (err) {
                vscode.window.showErrorMessage(err.message);
            }
        })
    );


    context.subscriptions.push(
        vscode.commands.registerCommand("gsn.generate-model-template", async (uri: vscode.Uri | undefined) => {
            if (!uri) {
                vscode.window.showErrorMessage('TODO: Support this');
                return;
            }

            const res = await generateNewModel(uri, 'new-model');

            vscode.window.showInformationMessage(`Created template model at ${res.path}`);
        })
    );


    context.subscriptions.push(vscode.workspace.onDidChangeConfiguration(async (event) => {
        const depiActivationChanged = event.affectsConfiguration('gsnGraph.enableDepi');
        if (depiActivationChanged) {
            const { enableDepi } = getUserPreferences();
            await vscode.window.showInformationMessage(`Depi was ${enableDepi ? 'activated' : 'deactivated'} - vscode will reload.`, 'OK');
            vscode.commands.executeCommand('workbench.action.reloadWindow');
        }
    }));

    // enable tracing (.Off, .Messages, Verbose)
    await lc.setTrace(Trace.Verbose);
    try {
        await lc.start();
    } catch (err) {
        log('ERROR: Failed to start Java Language Server:');
        log(err.message);
        vscode.window.showErrorMessage('GSN Assurance failed to start Java Language Server');
        vscode.window.showErrorMessage('Make sure you have Java 8+ installed!');
        return;
    }

    log('Java Language Server started ...');
    const distUris = await getDistUris(context.extensionUri);

    async function showGraphEditor(dirPath: string, nodePath: string | null) {
        const userPreferences = getUserPreferences();

        log(`User-preferences ${JSON.stringify(userPreferences)}`);
        // Update the state holding model context.
        const oldDirUri = modelContext.dirUri;
        modelContext.dirUri = vscode.Uri.file(dirPath);

        log(`Model dir: ${dirPath}`);

        if (modelHasDirtyFiles(dirPath)) {
            vscode.window.showInformationMessage(
                `The .gsn-documents are not persisted - save files before opening editor.`
            );

            // Set back to to previously opened context (if there was one).
            modelContext.dirUri = oldDirUri;
            return;
        }

        modelContext.undoStack = [];
        modelContext.redoStack = [];

        if (userPreferences.enableDepi) {
            if (modelContext.gsnDepi) {
                modelContext.gsnDepi.updateModelDir(modelContext.dirUri);
            } else {
                log('Depi is enabled, creating new GsnDepi instance.');
                modelContext.gsnDepi = new GsnDepi(git, modelContext.dirUri, log);
            }
        }

        if (!modelContext.gsnReview) {
            log('Creating new GsnReview instance.');
            modelContext.gsnReview = new GsnReview(git, modelContext.dirUri, log, modelContext.gsnDepi);
        } else {
            modelContext.gsnReview.updateModelDir(modelContext.dirUri);
        }

        if (panel) {
            log('Panel already existed - revealing it with new state..');
            panel.reveal();
        } else {
            log('No panel active - registering new event-listeners..');
            panel = vscode.window.createWebviewPanel('graph', 'GSN-Graph', vscode.ViewColumn.One, {
                retainContextWhenHidden: true,
                enableScripts: true,
            });

            const toDispose = [];

            toDispose.push(
                vscode.workspace.onDidSaveTextDocument(async (event) => {
                    const fpath = event.uri.path;

                    if (fpath.endsWith(CONSTANTS.FILE_EXTENSION) && modelContext.dirUri && fpath.startsWith(modelContext.dirUri.path)) {
                        log(`\nModel was updated via file: ${fpath}`);
                        modelContext.undoStack = [];
                        modelContext.redoStack = [];
                        try {
                            await emitUndoRedoAvailable(modelContext, panel, log);
                            const modelStr = await postCommandToLSP(log, CONSTANTS.LSP.GET_MODEL_JSON_COMMAND,
                                { modelDir: modelContext.dirUri.path });
                            await checkAndSendModelToGraph(panel, log, modelStr);
                            modelContext.modelHash = await readInModelHash(modelContext.dirUri);
                        } catch (err) {
                            await panel.webview.postMessage({
                                type: CONSTANTS.EVENTS.TYPES.ERROR_MESSAGE,
                                value: err.message,
                            });
                        }
                    }
                })
            );

            const graphEventHandler = getGraphEventHandler(modelContext, panel, git, log);
            toDispose.push(panel.webview.onDidReceiveMessage(graphEventHandler));

            panel.onDidDispose(
                async () => {
                    panel = null;
                    modelContext.dirUri = null;
                    modelContext.modelHash = null;
                    if (modelContext.gsnDepi) {
                        await modelContext.gsnDepi.destroy();
                        modelContext.gsnDepi = null;
                    }

                    modelContext.gsnReview = null;
                    modelContext.undoStack = [];
                    modelContext.redoStack = [];
                    toDispose.forEach((d) => d.dispose());
                    log('Webview panel is disposed.');
                },
                undefined,
                context.subscriptions
            );
        }

        Object.keys(distUris).forEach((name) => {
            distUris[name] = panel.webview.asWebviewUri(distUris[name]);
            log(`${name}: ${distUris[name].toString()}`);
        });

        const currentThemeKind = vscode.window.activeColorTheme.kind;
        const isDarkTheme = currentThemeKind === vscode.ColorThemeKind.Dark;

        log(`Is editor dark-mode? ${isDarkTheme}`);
        if (userPreferences.lightMode) {
            log(`lightMode enforced so wont use dark-mode`);
        }

        const webviewContent = getWebviewContent(distUris, userPreferences,
            userPreferences.lightMode ? false : isDarkTheme, nodePath);
        log(webviewContent);
        panel.webview.html = webviewContent;
        log('Done - graph-editor ready!');
    }

    context.subscriptions.push(
        vscode.commands.registerCommand('gsn.graph-editor', async () => {
            log(`\n ### New Graph Editor opened ###`);
            const editor = vscode.window.activeTextEditor;

            if (!editor || !editor.document || !editor.document.uri.fsPath.endsWith(CONSTANTS.FILE_EXTENSION)) {
                vscode.window.showInformationMessage(`GSN Graph Editor must be activated from an open .gsn-document.`);
                return;
            }

            const modelDirPath = path.dirname(editor.document.uri.fsPath);

            await showGraphEditor(modelDirPath, null);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('gsn.revealDepiResource', async (resource: Resource, branchName?: string) => {
            log('revealDepiResource', JSON.stringify(resource), branchName);
            const [gitUrl, relModelDir] = resource.resourceGroupUrl.split(CONSTANTS.DEPI.GIT_URL_END_CHAR);

            const repo = await tryFindGitRepoAtResourceGroupUrl(git, gitUrl, log);
            if (repo) {
                log('Local repo commit: [', repo.state.HEAD?.commit, '] resource: [', resource.resourceGroupVersion, ']');
                if (repo.state.HEAD?.commit === resource.resourceGroupVersion) {
                    const modelDirPath = path.join(getRepoRoothPath(repo), relModelDir);
                    await showGraphEditor(modelDirPath, resource.url.substring(1)); // Drop leading /
                    return;
                }
                vscode.window.showInformationMessage(
                    'Found local copy of repository but versions do not match - attempting to reveal in browser..'
                );
            } else {
                vscode.window.showInformationMessage(
                    'Repository not opened in vscode instance - attempting to reveal in browser..'
                );
            }

            let configuration = vscode.workspace.getConfiguration('depi');
            const gitPlatform = configuration.get<string>('git_collaboration_platform')!;

            if (gitPlatform === 'other') {
                vscode.window.showErrorMessage('Cannot reveal resource using unknown git-platform.');
                return;
            }

            const resourceUrl = relModelDir.startsWith('/') ? relModelDir : `/${relModelDir}`;

            await revealGitResourceInBrowser(gitPlatform, gitUrl, resource.resourceGroupVersion, resourceUrl, log);
        })
    );

    log('Activation done!');
}

export function deactivate() {
    return lc.stop();
}

function getWebviewContent({ jsBundleUri, cssBundleUri }, userPreferences: object, isDarkTheme: boolean, nodePath: string) {
    return `<!DOCTYPE html>
  <html lang="en">
  <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <link href="${cssBundleUri}" rel="stylesheet">
      <title>GSN</title>
  </head>
  <body style="color: ${isDarkTheme ? '#fff' : '#212B36'}; background-color: ${isDarkTheme ? 'rgb(18 18 18)' : '#fff'}; padding: 0; font-family: 'Roboto','Helvetica','Arial',sans-serif;">
    <div
        id="root"
        data-ts="${Date.now() /* Make sure it's unique so it doesn't keep any old model/state cached. */}"
        data-user-preferences='${JSON.stringify(userPreferences)}'
        data-dark-mode="${isDarkTheme}"
        data-node-id="${nodePath}"
    ></div>
    <script src="${jsBundleUri}"></script>
  </body>
  </html>`;
}

module.exports = {
    activate,
    deactivate,
};

async function getDistUris(extensionUri: vscode.Uri) {
    const assetManifestUri = vscode.Uri.joinPath(extensionUri, 'dist', 'bundle', 'asset-manifest.json');
    try {
        const readData = await vscode.workspace.fs.readFile(assetManifestUri);
        const manifest = JSON.parse(Buffer.from(readData).toString('utf8'));
        return {
            jsBundleUri: vscode.Uri.joinPath(extensionUri, 'dist', 'bundle', manifest.files['main.js']),
            cssBundleUri: vscode.Uri.joinPath(extensionUri, 'dist', 'bundle', manifest.files['main.css']),
        };
    } catch (err) {
        if (err.code === 'FileNotFound') {
            throw new Error('Could not find asset-manifest.json - did you run "npm build"?');
        }
        throw err;
    }
}

function modelHasDirtyFiles(dirPath: string): boolean {
    const dirtyFiles = [];

    vscode.window.tabGroups.all.flatMap(({ tabs }) =>
        tabs.map((tab: any) => {
            if (!tab || !tab.input || !tab.input.uri) {
                return tab;
            }

            const fpath = tab.input.uri.path;
            if (tab.isDirty && fpath.endsWith('.gsn') && fpath.startsWith(dirPath)) {
                dirtyFiles.push(fpath);
            }

            return tab;
        })
    );

    return dirtyFiles.length > 0;
}