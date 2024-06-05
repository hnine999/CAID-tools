import * as crypto from 'crypto';
import * as vscode from 'vscode';
import { randomUUID } from 'crypto';
import CONSTANTS from './CONSTANTS';
import { Tarjan } from 'tarjan-scc';

/**
 * Computes the SHA1 hash of a given string.
 *
 * @param {string} str - The input string for which the hash will be computed.
 * @returns {string} - The SHA1 hash of the input string.
 */
export function getSHA1Hash(str: string): string {
    return crypto.createHash('sha1').update(str, 'utf-8').digest('hex');
}

/**
 * Generate a simple gsn model inside a directory.
 * @param {vscode.Uri} uri - File or directory where to put the new model
 * @returns {Promise<vscode.Uri>} A promise that resolves to the directory URI where file generated.
 */
export async function generateNewModel(uri: vscode.Uri, dirname: string, contents: Map<string, string>|undefined=undefined): Promise<vscode.Uri> {
    const modelTemplatStr = `GOALS model
    goal G1
        summary "This is the top-goal"
`;
    const parentDir = await getNearestDirectory(uri);
    const modelDir = await createUniqueDirectory(parentDir, dirname);
    if (contents) {
        for (const [name, content] of contents) {
            await vscode.workspace.fs.writeFile(vscode.Uri.joinPath(modelDir, `${name}.gsn`), Buffer.from(content, 'utf8'));
        }
    } else {
        await vscode.workspace.fs.writeFile(vscode.Uri.joinPath(modelDir, 'assurance.gsn'), Buffer.from(modelTemplatStr, 'utf8'));
    }
    return modelDir;
}

/**
 * Gets the parent directory of a file and the directory itself if a dir is given.
 * @param {vscode.Uri} uri - The URI to resolve.
 * @returns {Promise<vscode.Uri>} A promise that resolves to the directory URI.
 */
export async function getNearestDirectory(uri: vscode.Uri): Promise<vscode.Uri> {
    const stat = await vscode.workspace.fs.stat(uri);
    
    if (stat.type === vscode.FileType.Directory) {
        return uri;
    }

    if (stat.type === vscode.FileType.File) {
        return vscode.Uri.joinPath(uri, '..');
    }

    throw new Error(`Unknown uri type ${stat.type} - not file or folder.`);
}

/**
 * Creates a unique directory with the specified name under the given base URI.
 * If a directory with the same name already exists, a numerical suffix will be appended
 * to the directory name until a unique name is found.
 * @param {vscode.Uri} baseUri - The base URI under which to create the directory.
 * @param {string} dirName - The name of the directory to create.
 * @returns {Promise<vscode.Uri>} A promise that resolves to the URI of the created directory.
 */
export async function createUniqueDirectory(baseUri: vscode.Uri, dirName: string): Promise<vscode.Uri> {
    let i = 1;

    while (true) {
        const candidateDirName = i === 1 ? dirName : `${dirName}${i}`;

        const candidateDirUri = vscode.Uri.joinPath(baseUri, candidateDirName);

        if (!await directoryExists(candidateDirUri)) {
            await vscode.workspace.fs.createDirectory(candidateDirUri);
            return candidateDirUri;
        }
        i++;
    }
}

/**
 * Checks if a directory exists at the specified URI.
 * @param {vscode.Uri} uri - The URI to check.
 * @returns {Promise<boolean>} A promise that resolves to true if a directory exists at the URI, otherwise false.
 */
export async function directoryExists(uri: vscode.Uri): Promise<boolean> {
    try {
        await vscode.workspace.fs.stat(uri);
        return true;
    } catch {
        return false;
    }
}

/**
 * Computes a hash for the entire model based on individual file hashes.
 * This function takes an object where the keys are file names and the values are
 * their corresponding hashes. It sorts the file names, then concatenates the file names
 * and their hashes. Finally, it computes the SHA1 hash for the concatenated string,
 * which serves as the model hash.
 *
 * @param {object} fileNameToHash - An object with file names as keys and their corresponding hashes as values.
 * @returns {string} The computed SHA1 hash for the entire model.
 */
export function computeModelHash(fileNameToHash: object) : string {
    const namesHashes = [];
    Object.keys(fileNameToHash).sort().forEach((fileName) => {
        namesHashes.push(`${fileName}#${fileNameToHash[fileName]}`);
    });

    return getSHA1Hash(namesHashes.join(','));
}

/**
 * Computes a hash for the entire model based on individual file hashes.
 * This function takes a Map of file names to their content, calculates the
 * SHA1 hash for each file, and concatenates the file names and their hashes.
 * It then computes the SHA1 hash for the concatenated string, which serves as
 * the model hash.
 *
 * @param {Map<string, string>} modelFiles - A Map of file names to their content.
 * @returns {string} The computed SHA1 hash for the entire model.
 */
export function getModelHash(modelFiles: Map<string, string>) : string {
    const fileNameToHash = {};
    modelFiles.forEach((fileContent, fileName) => {
        fileNameToHash[fileName] = getSHA1Hash(fileContent);
    })

    return computeModelHash(fileNameToHash);
}

/**
 * Reads all the files in the model directory and computes the model hash.
 * This function first reads all the files in the given model directory using
 * the readModelFiles function. Then, it computes the model hash using the
 * getModelHash function.
 *
 * @param {vscode.Uri} modelDirUri - The Uri of the model directory.
 * @returns {Promise<string>} A Promise that resolves to the computed SHA1 hash for the entire model.
 */
export async function readInModelHash(modelDirUri: vscode.Uri) : Promise<string> {
    const modelFiles = await readModelFiles(modelDirUri);
    return getModelHash(modelFiles);
}

/**
 * Reads all model files with the extension '.gsn' from a specified directory and returns their contents in a Map.
 *
 * @param {vscode.Uri} modelDirUri - The directory URI containing the model files.
 * @returns {Promise<Map<string, string>>} - A Promise that resolves to a Map containing the filenames and their content as key-value pairs.
 */
export async function readModelFiles(modelDirUri: vscode.Uri): Promise<Map<string, string>> {
    const promises = [];
    const fileNames = [];
    const entries = await vscode.workspace.fs.readDirectory(modelDirUri);

    for (const [fileName, type] of entries) {
        if (type === vscode.FileType.File && fileName.endsWith(CONSTANTS.FILE_EXTENSION)) {
            fileNames.push(fileName);
            promises.push(vscode.workspace.fs.readFile(vscode.Uri.joinPath(modelDirUri, fileName)));
        }
    }

    const fileContents = await Promise.all(promises);

    const res = new Map<string, string>();
    for (let i = 0; i < fileNames.length; i += 1) {
        res.set(fileNames[i], Buffer.from(fileContents[i]).toString('utf8'));
    }

    return res;
}

/**
 * Writes new files to a specified directory.
 *
 * @param {vscode.Uri} modelDirUri - The directory URI where the new files will be written.
 * @param {Map<string, string>} newFiles - A Map containing the filenames and their content as key-value pairs.
 * @returns {Promise<void>} - A Promise that resolves when all files have been written.
 */
export async function writeModelFiles(modelDirUri: vscode.Uri, newFiles: Map<string, string>): Promise<void> {
    const promises = [];

    newFiles.forEach((content, fileName) => {
        promises.push(vscode.workspace.fs.writeFile(vscode.Uri.joinPath(modelDirUri, fileName), Buffer.from(content, 'utf8')));
    });

    await Promise.all(promises);
}

export async function readInViews(modelDirUri: vscode.Uri) {
    return await _readInJson(modelDirUri, CONSTANTS.VIEWS_FILENAME) || '[]';
}

export async function writeOutViews(modelDirUri: vscode.Uri, views: Array<object>) {
    return await _writeOutJson(modelDirUri, CONSTANTS.VIEWS_FILENAME, views);
}

export async function readInLabels(modelDirUri: vscode.Uri) {
    return await _readInJson(modelDirUri, CONSTANTS.LABELS_FILENAME) || '[]';
}

export async function writeOutLabels(modelDirUri: vscode.Uri, labels: Array<object>) {
    return await _writeOutJson(modelDirUri, CONSTANTS.LABELS_FILENAME, labels);
}

export async function readInReviewInfo(modelDirUri: vscode.Uri) {
    return JSON.parse(await _readInJson(modelDirUri, CONSTANTS.REVIEW_FILENAME) || '{"tag": null}');
}

export async function writeOutReviewInfo(modelDirUri: vscode.Uri, reviewInfo: object) {
    return await _writeOutJson(modelDirUri, CONSTANTS.REVIEW_FILENAME, reviewInfo);
}

export async function readInComments(modelDirUri: vscode.Uri) {
    return await _readInJson(modelDirUri, CONSTANTS.COMMENTS_FILENAME) || '{}';
}

export async function writeOutComments(modelDirUri: vscode.Uri, comments: object) {
    const orderedComments = {};
    Object.keys(comments).sort().forEach(key => orderedComments[key] = comments[key]);
    return await _writeOutJson(modelDirUri, CONSTANTS.COMMENTS_FILENAME, comments);
}

async function _readInJson(modelDirUri: vscode.Uri, fname: string) {
    const dirUri = vscode.Uri.joinPath(modelDirUri, CONSTANTS.STATE_DIRECTORY);
    const jsonUri = vscode.Uri.joinPath(dirUri, fname);
    try {
        const readData = await vscode.workspace.fs.readFile(jsonUri);
        return Buffer.from(readData).toString('utf8');
    } catch (err) {
        if (err.code === 'FileNotFound') {
            return null;
        }
        throw err;
    }
}

async function _writeOutJson(modelDirUri: vscode.Uri, fname: string, jsonArray: Array<object>|object) {
    const dirUri = vscode.Uri.joinPath(modelDirUri, CONSTANTS.STATE_DIRECTORY);
    try {
        const dir = await vscode.workspace.fs.stat(dirUri);
        if (dir.type !== vscode.FileType.Directory) {
            throw new Error(`The provided URI is not a directory: ${dirUri}`);
        }
    } catch (error) {
        if ((error as vscode.FileSystemError).code === 'FileNotFound') {
            await vscode.workspace.fs.createDirectory(dirUri);
        } else {
            console.error('An error occurred:', error);
        }
    }

    const uri = vscode.Uri.joinPath(dirUri, fname);
    const jsonStr = JSON.stringify(jsonArray, null, 2);
    await vscode.workspace.fs.writeFile(uri, Buffer.from(jsonStr, 'utf8'));
}

export function getChangeMessage(changeArray: any[]) {
    if (changeArray.length === 1) {
        return `${changeArray[0].cmd} ${changeArray[0].nodeId.split('/').pop()}`;
    } else {
        return `${changeArray[0].cmd} + [${changeArray.length - 1}] change(s)`;
    }
}

// Consider reusing json2gsn for more checks here.
export function checkModelForLoops(gsnModel: any[]): boolean {
    const t = new Tarjan();

    for (const node of gsnModel) {
        let relations = [];
        if (node.solvedBy) {
            relations = node.solvedBy;
        }

        if (node.inContextOf) {
            relations = [...relations, ...node.inContextOf];
        }

        t.addVertex(node.id);
        for (const childId of relations) {
            t.addVertex(childId);
            t.connectVertices(node.id, childId);
        }
    }

    return t.hasLoops();
}