import * as vscode from 'vscode';
import * as path from 'path';

import { getUndoRedoEntry, applyRedo, applyUndo } from './undoRedo';
import CONSTANTS from './CONSTANTS';
import { API as GitAPI } from './@types/git';
import { ModelContext, View, Label, Comment, CommentUpdate } from './@types/gsn';
import {
    readInModelHash,
    readInViews,
    writeOutViews,
    readInLabels,
    writeOutLabels,
    getChangeMessage,
    readModelFiles,
    getModelHash,
    checkModelForLoops,
    readInComments,
    writeOutComments
} from './util';
import { tryGetGitUser } from './gitUtils';

export default function getGraphEventHandler(modelContext: ModelContext, panel: vscode.WebviewPanel, git: GitAPI, log: any) {
    let userName = '';
    let email = '';

    async function requestModel() {
        log('Model was requested from Graph-Editor');
        const modelStr = await postCommandToLSP(log, CONSTANTS.LSP.GET_MODEL_JSON_COMMAND,
            { modelDir: modelContext.dirUri.path });
        await checkAndSendModelToGraph(panel, log, modelStr);
        modelContext.modelHash = await readInModelHash(modelContext.dirUri);
        modelContext.undoStack = [];
        modelContext.redoStack = [];
        await emitUndoRedoAvailable(modelContext, panel, log);
    }

    async function requestViews() {
        log('Views were requested from Graph-Editor');
        const viewsStr = await readInViews(modelContext.dirUri);
        await sendStateToGraph(panel, log, CONSTANTS.EVENTS.STATE_TYPES.VIEWS, viewsStr, null);
    }

    async function requestLabels() {
        log('Labels were requested from Graph-Editor');
        const labelsStr = await readInLabels(modelContext.dirUri);
        await sendStateToGraph(panel, log, CONSTANTS.EVENTS.STATE_TYPES.LABELS, labelsStr, null);
    }

    async function requestComments() {
        log('Comments were requested from Graph-Editor');
        const commentsStr = await readInComments(modelContext.dirUri);
        await sendStateToGraph(panel, log, CONSTANTS.EVENTS.STATE_TYPES.COMMENTS, commentsStr, null);
    }

    async function requestDepiResources() {
        log('DepiResources were requested from Graph-Editor');
        const resources = await modelContext.gsnDepi.getAllResources();
        await sendStateToGraph(panel, log, CONSTANTS.EVENTS.STATE_TYPES.DEPI_RESOURCES, '', resources);
    }

    async function stateUpdateModel(value: any[]) {
        const argument = {
            modelDir: modelContext.dirUri.path,
            commandList: value
        };
        await emitUndoRedoAvailable(modelContext, panel, log, true);
        const baseFiles = await readModelFiles(modelContext.dirUri);
        const modelHash = getModelHash(baseFiles);

        if (modelContext.modelHash !== modelHash) {
            throw new Error('Unknown changes were made to model - will not apply change');
        }

        const modelStr = await postCommandToLSP(log, CONSTANTS.LSP.MODEL_UPDATE_COMMAND, argument);
        const undoRedoEntry = await getUndoRedoEntry(modelContext.dirUri, baseFiles, getChangeMessage(value));

        log(`Updated files: ${undoRedoEntry.getUpdatedFiles().join(', ')}`);
        await checkAndSendModelToGraph(panel, log, modelStr);

        modelContext.modelHash = undoRedoEntry.getNewModelHash();
        modelContext.undoStack.push(undoRedoEntry);
        modelContext.redoStack = [];
        if (modelContext.undoStack.length > CONSTANTS.MAX_NUMBER_OF_UNDO) {
            log(`Undo queue full at ${CONSTANTS.MAX_NUMBER_OF_UNDO} entries, removing oldest`);
            modelContext.undoStack.shift();
        }

        await emitUndoRedoAvailable(modelContext, panel, log);
    }

    async function stateUpdateViews(value: View[]) {
        log('Writing new views to views.json');
        await writeOutViews(modelContext.dirUri, value);
    }

    async function stateUpdateLabels(value: Label[]) {
        log('Writing new labels to labels.json');
        await writeOutLabels(modelContext.dirUri, value);
    }

    async function stateUpdateComments(value: CommentUpdate) {
        const comments = JSON.parse(await readInComments(modelContext.dirUri));
        if (value.isNew) {
            log('Adding new comment', JSON.stringify(value));
            const user = await tryGetGitUser(git, modelContext.dirUri, log);
            if (user.name) {
                userName = user.name;
                email = user.email;
            } else if (!userName) {
                userName = await vscode.window.showInputBox({
                    prompt: 'No user name setup for git repository',
                    placeHolder: 'Enter a name for the comment here...',
                });
                email = 'uknown';
            }

            if (!userName) {
                vscode.window.showErrorMessage('No user name provided, will not persist comment!');
                return;
            }

            const newComment: Comment = {
                comment: value.comment as string,
                timestamp: Date.now(),
                user: { name: userName, email }
            };
            if (!comments[value.uuid]) {
                comments[value.uuid] = [];
            }

            comments[value.uuid].unshift(newComment);
        } else {
            log('Deleting comment', JSON.stringify(value));
            const indexToRemove = (comments[value.uuid] || [])
                .findIndex((comment: Comment) => comment.timestamp === value.timestamp);

            if (indexToRemove < 0) {
                log('Could not find matching comment', value.uuid, value.timestamp);
                return;
            }

            comments[value.uuid].splice(indexToRemove, 1);
            if (comments[value.uuid].length === 0) {
                delete comments[value.uuid];
            }
        }

        writeOutComments(modelContext.dirUri, comments);
        await sendStateToGraph(panel, log, CONSTANTS.EVENTS.STATE_TYPES.COMMENTS, JSON.stringify(comments), comments);
    }

    async function revealOrigin(nodeId: string) {
        log(`Open Document for ${nodeId}`);
        const argument = {
            modelDir: modelContext.dirUri.path,
            nodeId,
        };

        let fileUri: vscode.Uri;
        try {
            const returnStr = await postCommandToLSP(log, CONSTANTS.LSP.REVEAL_ORIGIN_COMMAND, argument);
            const { filePath, lineNumber } = JSON.parse(returnStr);
            fileUri = vscode.Uri.joinPath(modelContext.dirUri, path.basename(filePath));
            await vscode.workspace.fs.stat(fileUri);
            vscode.window.showTextDocument(fileUri, {
                viewColumn: vscode.ViewColumn.Active,
                preview: false,
                selection: new vscode.Range(lineNumber - 1, 0, lineNumber, 0)
            });
        } catch (err) {
            if (err.code === 'FileNotFound') {
                log(fileUri.toString());
                vscode.window.showInformationMessage(`No such file ${fileUri.path}`);
            } else {
                vscode.window.showInformationMessage(err.message);
            }
        }
    }

    async function undo() {
        const undoRedoEntry = modelContext.undoStack.pop();
        if (!undoRedoEntry) {
            throw new Error('Nothing in undo-queue - cannot undo');
        }

        log(`Applying undo for "${undoRedoEntry.message}"`);
        const changedFiles = await applyUndo(modelContext.dirUri, undoRedoEntry);
        log(`Undid files: ${changedFiles.join(', ')}`);

        const modelStr = await postCommandToLSP(log, CONSTANTS.LSP.GET_MODEL_JSON_COMMAND,
            { modelDir: modelContext.dirUri.path });
        await checkAndSendModelToGraph(panel, log, modelStr);

        modelContext.modelHash = undoRedoEntry.getBaseModelHash();
        modelContext.redoStack.push(undoRedoEntry);
        await emitUndoRedoAvailable(modelContext, panel, log);
    }

    async function redo() {
        const undoRedoEntry = modelContext.redoStack.pop();
        if (!undoRedoEntry) {
            throw new Error('Nothing in queue - cannot undo');
        }

        log(`Applying redo for "${undoRedoEntry.message}"`);
        const changedFiles = await applyRedo(modelContext.dirUri, undoRedoEntry);
        log(`Redid files: ${changedFiles.join(', ')}`);

        const modelStr = await postCommandToLSP(log, CONSTANTS.LSP.GET_MODEL_JSON_COMMAND,
            { modelDir: modelContext.dirUri.path });

        await checkAndSendModelToGraph(panel, log, modelStr);

        modelContext.modelHash = undoRedoEntry.getNewModelHash();
        modelContext.undoStack.push(undoRedoEntry);
        await emitUndoRedoAvailable(modelContext, panel, log);
    }

    async function command(type: string, key: string, value: any, commandId: string) {
        log('Command requested from Graph-Editor', type, key);
        try {
            const typeObj = type === CONSTANTS.EVENTS.TYPES.DEPI_CMD ? modelContext.gsnDepi : modelContext.gsnReview;
            const res = await typeObj[key](value);
            log('Sending results', JSON.stringify(res));
            await panel.webview.postMessage({
                type,
                commandId,
                value: res,
            });
        } catch (err) {
            log('Failed processing command', err);
            await panel.webview.postMessage({
                type,
                commandId,
                error: err.message,
            });
        }
    }

    async function processMessage(message: any) {
        const { type, key, value } = message;
        log(`Got message from graph-editor: ${JSON.stringify(message)}`);
        switch (type) {
            case CONSTANTS.EVENTS.TYPES.REQUEST_MODEL:
                await requestModel();
                break;
            case CONSTANTS.EVENTS.TYPES.REQUEST_VIEWS:
                await requestViews();
                break;
            case CONSTANTS.EVENTS.TYPES.REQUEST_LABELS:
                await requestLabels();
                break;
            case CONSTANTS.EVENTS.TYPES.REQUEST_COMMENTS:
                await requestComments();
                break;
            case CONSTANTS.EVENTS.TYPES.REQUEST_DEPI_RESOURCES:
                await requestDepiResources();
                break;
            case CONSTANTS.EVENTS.TYPES.STATE_UPDATE:
                if (key === CONSTANTS.EVENTS.STATE_TYPES.MODEL) {
                    await stateUpdateModel(value);
                } else if (key === CONSTANTS.EVENTS.STATE_TYPES.VIEWS) {
                    await stateUpdateViews(value);
                } else if (key === CONSTANTS.EVENTS.STATE_TYPES.LABELS) {
                    await stateUpdateLabels(value);
                } else if (key === CONSTANTS.EVENTS.STATE_TYPES.COMMENTS) {
                    await stateUpdateComments(value);
                }
                break;
            case CONSTANTS.EVENTS.TYPES.REVEAL_ORIGIN:
                const { nodeId } = value;
                await revealOrigin(nodeId);
                break;
            case CONSTANTS.EVENTS.TYPES.UNDO:
                await undo();
                break;
            case CONSTANTS.EVENTS.TYPES.REDO:
                await redo();
                break;
            case CONSTANTS.EVENTS.TYPES.DEPI_CMD:
            case CONSTANTS.EVENTS.TYPES.REVIEW_CMD:
                await command(type, key, value, message.commandId);
                break;
            default:
                break;
        }
    }

    const eventJobQueue = [];
    let working = false;

    async function processNextJob() {
        if (working || eventJobQueue.length === 0) {
            return;
        }

        working = true;
        try {
            await processMessage(eventJobQueue.shift());
            working = false;
            setTimeout(processNextJob);
        } catch (err) {
            log(err.message);
            console.error(err);
            await panel.webview.postMessage({
                type: CONSTANTS.EVENTS.TYPES.ERROR_MESSAGE,
                value: err.message,
            });
        }
    }

    if (modelContext.gsnDepi) {
        modelContext.gsnDepi.addDepiWatcher(async () => {
            try {
                await requestDepiResources();
            } catch (err) {
                log(err);
            }
        });
    }

    return function eventHandler(message: any) {
        eventJobQueue.push(message);
        processNextJob();
    }
}

// Helper functions

async function sendStateToGraph(panel: vscode.WebviewPanel, log: any, stateType: string, valueStr: string, value: any) {
    log(`Sending updated ${stateType}: ${valueStr ? valueStr.substring(0, 100) : 'No state string provided'}...`);
    if (!panel) {
        // This should never happen..
        log('Cannot send to graph when panel not intialized... (why is it not?)');
        return;
    }

    await panel.webview.postMessage({
        type: CONSTANTS.EVENTS.TYPES.STATE_UPDATE,
        key: stateType,
        value: value || JSON.parse(valueStr),
    });
}

export async function checkAndSendModelToGraph(panel: vscode.WebviewPanel, log: any, modelStr: string) {
    const gsnModel = JSON.parse(modelStr);
    if (checkModelForLoops(gsnModel)) {
        throw new Error('Model contains loops - these must be broken up by removing relations.');
    }

    await sendStateToGraph(panel, log, CONSTANTS.EVENTS.STATE_TYPES.MODEL, modelStr, gsnModel);
}

export async function emitUndoRedoAvailable(modelContext: ModelContext, panel: vscode.WebviewPanel, log: any, forceFalse: boolean = false) {
    // forceFalse is there to avoid race-conditions while updates are computed.
    const value = {
        undo: forceFalse ? 0 : modelContext.undoStack.length,
        redo: forceFalse ? 0 : modelContext.redoStack.length,
    };

    log(`Emitting UNDO/REDO available: ${JSON.stringify(value)}`);
    await panel.webview.postMessage({
        type: CONSTANTS.EVENTS.TYPES.UNDO_REDO_AVAILABLE,
        value,
    });
}

export async function postCommandToLSP(log: any, command: string, argument: object) {
    log(`Will post to LSP Command: ${command}, arg: ${JSON.stringify(argument)}`);
    const responseStr = await vscode.commands.executeCommand(command, argument) as string;
    log(`Response: ${responseStr && responseStr.substring(0, 100)}...`);

    try {
        const parsed = JSON.parse(responseStr);
        if (typeof parsed === 'string') {
            throw new Error(parsed);
        }
    } catch (err) {
        console.error(err);
        throw new Error(responseStr);
    }

    return responseStr;
}
