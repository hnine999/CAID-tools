import * as vscode from 'vscode';
import { Resource } from 'depi-node-client';
import { getGraphEventHandler } from './graphEventHandler';
import DepiState from './DepiState';

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

let panel: vscode.WebviewPanel | null;
let depiState: DepiState | null;
let channel: vscode.OutputChannel;

let manuallyDisposing = false;
let toDispose: vscode.Disposable[] = [];
async function disposeOfState() {
    panel?.dispose();
    panel = null;
    toDispose.forEach((d) => d.dispose());
    toDispose = [];
    await depiState?.destroy();
    depiState = null;
}

export function activate(context: vscode.ExtensionContext) {
    channel = vscode.window.createOutputChannel('webgme-depi');
    channel.show(); // TODO: Remove!

    log('webgme-depi extension activating..');

    async function displayWebGMEPanel(webgmeUrl: string, depiBranchName = 'main') {
        let configuration = vscode.workspace.getConfiguration('webgme-depi');
        if (!webgmeUrl) {
            const urls = configuration.get<string[]>('urls') as string[];
            if (!urls || urls.length === 0) {
                webgmeUrl = await vscode.window.showInputBox({
                    prompt: 'No urls for webgme configured - manually provide one.',
                    placeHolder: 'E.g. http://127.0.0.1:8080/',
                    value: '',
                    validateInput: (text: string) => {
                        const val = text.toLowerCase();
                        if (val.substring(0, 8) !== 'https://' || val.substring(0, 7) !== 'http://') {
                            return ''
                        }
                        return null;
                    }
                }) || '';
            } else if (urls.length === 1) {
                webgmeUrl = urls[0];
            } else {
                webgmeUrl = await vscode.window.showQuickPick(urls, {
                    placeHolder: 'Select webgme url...',
                }) || '';
            }
        }

        if (!webgmeUrl) {
            vscode.window.showErrorMessage('No webgme-url provided..');
            return;
        }

        log('displayWebGMEPanel, url', webgmeUrl);

        if (panel) {
            log('Panel instance already available - will dispose of it');
            manuallyDisposing = true;
            await disposeOfState();
        }

        depiState = new DepiState(log);
        panel = vscode.window.createWebviewPanel(
            'graph',
            'WebGME Editor',
            vscode.ViewColumn.Active,
            {
                retainContextWhenHidden: true,
                enableScripts: true,
            }
        );

        toDispose.push(panel.webview.onDidReceiveMessage(await getGraphEventHandler(panel, depiState, depiBranchName, log)));

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

        panel.webview.html = getWebviewContent(webgmeUrl);
    }

    context.subscriptions.push(vscode.commands.registerCommand('webgme-depi.modelingEditor', displayWebGMEPanel));
    context.subscriptions.push(
        vscode.commands.registerCommand('webgme-depi.revealDepiResource', async (resource: Resource, branchName?: string) => {
            log('revealDepiResource', JSON.stringify(resource));
            let nodeId = resource.url === '' ? 'root' : resource.url;

            if (nodeId.endsWith('/')) {
                nodeId = nodeId.substring(0, nodeId.length - 1);
            }

            // FIXME: Isn't there a built-in for this??
            const webgmeUrl = `${resource.resourceGroupUrl}&commit=${resource.resourceGroupVersion}&node=${nodeId}`;
            const [baseUrl, query] = webgmeUrl.split('?');
            const encodedQuery = query.split('&').map(q => {
                const [name, value] = q.split('=');
                return [name, encodeURIComponent(value)].join('=');
            }).join('&');
            const encodedUrl = encodeURI([baseUrl, encodedQuery].join('?'));
            // log('Opening up browser', encodedUrl);
            // await vscode.env.openExternal(vscode.Uri.parse(encodedUrl));
            await displayWebGMEPanel(encodedUrl);
        }));

    log('webgme-depi activation done!');
}

function getWebviewContent(url: string) {
    return `<!DOCTYPE html>
  <html lang="en">
  <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Modeling</title>
  </head>
  <body data-ts="${Date.now() /* Make sure it's unique so it doesn't keep any old model/state cached. */}">
    <script>
        (() => {
            const vscode = acquireVsCodeApi();
            let webgmeFrameWindow;

            window.addEventListener('message', event => {
                console.log('message in webView ' + JSON.stringify(event.data));
                if (!webgmeFrameWindow) {
                    webgmeFrameWindow = document.getElementById('webgme-frame').contentWindow;
                }

                if (event.source !== webgmeFrameWindow) {
                    console.log('Forwarding to webgme-frame..');
                    webgmeFrameWindow.postMessage(event.data, '*');
                } else {
                    console.log('Sending to vscode process..');
                    vscode.postMessage(event.data);
                }
            });
        })();
    </script>
    <iframe id="webgme-frame" src="${url}" width="98%" height="98%" style="position: absolute; min-width:1024px; min-height:768px;"/>
  </body>
  </html>`;
}

export function deactivate() { }
