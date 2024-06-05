import * as vscode from 'vscode';
import * as fs from 'fs/promises';
import * as path from 'path';
import { API as GitAPI, GitExtension, Repository } from './@types/git';
import { Resource } from 'depi-node-client';

const IS_WINDOWS = process.platform === 'win32';

export function getLinuxPath(anyPath: string): string {
    return anyPath.replace(/\\/g, '/');
}

export function getRepoRoothPath(repo: Repository) {
    const repoRootPath = getLinuxPath(repo.rootUri.path);
    if (IS_WINDOWS) {
        // Remove leading "/"" in "/c:/dir1/dir2"
        return repoRootPath.substring(1);
    }

    return repoRootPath;
}

function getRemoteRepoUrl(repo: Repository) {
    if (repo!.state.remotes.length > 0 && repo!.state.remotes[0].fetchUrl) {
        return repo!.state.remotes[0].fetchUrl;
    }

    return null;
}

export async function getGitApi(): Promise<GitAPI> {
    const extension = vscode.extensions.getExtension('vscode.git') as vscode.Extension<GitExtension>;
    if (extension) {
        const gitExtension = extension.isActive ? extension.exports : await extension.activate();

        return gitExtension.getAPI(1);
    } else {
        throw new Error('Could not load git-api from vscode extension');
    }
}

export function tryResolveResourceGroupUrl(resourceGroupUrl: string, gitUrls: string[], log: Function) {
    const { owner, name } = parseResourceGroupUrl(resourceGroupUrl);
    let rgUrl: string | null = null;
    // Try to find matching resource-group based on
    for (const gitUrl of gitUrls) {
        const { owner: otherOwner, name: otherName } = parseResourceGroupUrl(gitUrl);
        if (owner === otherOwner && name === otherName) {
            rgUrl = gitUrl;
            break;
        }
    }

    if (rgUrl) {
        log('Found matching resource-group', rgUrl, 'for', resourceGroupUrl);
    } else {
        log('Could not find matching resource-group, using local url as host', resourceGroupUrl);
    }

    return rgUrl;
}

export async function tryFindGitRepoForUri(git: GitAPI, uri: vscode.Uri): Promise<Repository | null> {
    const filePath = getLinuxPath(uri.fsPath);
    let repoRootPath: string | null = null;

    for (const repo of git.repositories) {
        await repo.status();

        repoRootPath = getRepoRoothPath(repo);

        if (filePath.startsWith(repoRootPath)) {
            return repo;
        }
    }

    return null;
}

export async function tryFindGitRepoAtResourceGroupUrl(
    git: GitAPI,
    resourceGroupUrl: string,
    log: Function
): Promise<Repository | null> {
    const gitUrls = new Map<string, Repository>();

    for (const repo of git.repositories) {
        await repo.status();

        const gitUrl = getRemoteRepoUrl(repo);

        if (!gitUrl) {
            continue;
        }

        gitUrls.set(gitUrl, repo);
    }

    const gitUrl = tryResolveResourceGroupUrl(resourceGroupUrl, [...gitUrls.keys()], log);

    if (!gitUrl) {
        return null;
    }

    return gitUrls.get(gitUrl) as Repository;
}

export async function getGitResourceInfoFromPath(
    git: GitAPI,
    uri: vscode.Uri
): Promise<{ gitUrl: string; commitVersion: string; resourceRelativePath: string }> {
    const filePath = getLinuxPath(uri.fsPath);
    const repo = await tryFindGitRepoForUri(git, uri);

    if (!repo) {
        vscode.window.showInformationMessage('Resource must be a in a git repository that is opened in vscode.');
        vscode.window.showInformationMessage('HINT: add setting "git.openRepositoryInParentFolders": "always"');
        throw new Error(`Could not find open git-repo for "${path.basename(uri.fsPath)}"`);
    }

    const gitUrl = getRemoteRepoUrl(repo);
    const commitVersion = repo.state.HEAD?.commit;

    if (!gitUrl) {
        throw new Error('Could not obtain a remote for the git repository!');
    }

    if (!commitVersion) {
        throw new Error('Could not obtain a version for the git repository!');
    }

    let resourceRelativePath = filePath.substring(getRepoRoothPath(repo).length + 1);

    const stat = await fs.stat(filePath);

    if (stat.isDirectory()) {
        resourceRelativePath += '/';
    }

    return { gitUrl, commitVersion, resourceRelativePath };
}

export function parseResourceGroupUrl(resourceGroupUrl: string) {
    // git@git.isis.vanderbilt.edu:aa-caid/depi-impl.git
    // http://localhost:3001/patrik/c-sources.git
    // git@github.com:webgme/webgme.git
    // https://git.isis.vanderbilt.edu/aa-caid/depi-impl.git
    // git-vandy:VUISIS/p-state-visualizer.git

    const lastSlashIndex = resourceGroupUrl.lastIndexOf('/');
    let hostDividerIndex = 0;
    let host = '';
    let hostName = '';
    let hostPrefix = '';
    let isSsh = false;

    const isHttp = resourceGroupUrl.startsWith('http://');
    const isHttps = resourceGroupUrl.startsWith('https://');

    if (isHttp || isHttps) {
        isSsh = false;
        hostDividerIndex = resourceGroupUrl.lastIndexOf('/', lastSlashIndex - 1);
        host = resourceGroupUrl.substring(0, hostDividerIndex);
        if (isHttp) {
            hostPrefix = 'http://';
            hostName = host.substring('http://'.length);
        } else {
            hostPrefix = 'https://';
            hostName = host.substring('https://'.length);
        }
    } else {
        // ssh
        isSsh = true;
        hostDividerIndex = resourceGroupUrl.lastIndexOf(':');
        host = resourceGroupUrl.substring(0, hostDividerIndex);
        const atIndex = host.indexOf('@');
        if (atIndex > -1) {
            hostPrefix = host.substring(0, atIndex + 1);
            hostName = host.substring(atIndex + 1);
        } else {
            hostName = host;
            hostPrefix = '';
        }
    }

    const owner = resourceGroupUrl.substring(hostDividerIndex + 1, lastSlashIndex);
    const name = resourceGroupUrl.substring(lastSlashIndex + 1, resourceGroupUrl.length).replace(/\.git$/, '');

    return { host, owner, name, hostName, hostPrefix, isSsh };
}

export async function revealGitResource(git: GitAPI, gitPlatform: string, resource: Resource, log: Function) {
    const repo = await tryFindGitRepoAtResourceGroupUrl(git, resource.resourceGroupUrl, log);
    if (repo) {
        log('Local repo commit: [', repo.state.HEAD?.commit, '] resource: [', resource.resourceGroupVersion, ']');
        if (repo.state.HEAD?.commit === resource.resourceGroupVersion) {
            const repoRootPath = getRepoRoothPath(repo);
            const resourceUri = vscode.Uri.file(path.join(repoRootPath, resource.url));
            console.log(resourceUri);
            if (!resource.url.endsWith('/')) {
                try {
                    await vscode.workspace.fs.stat(resourceUri);
                    vscode.window.showTextDocument(resourceUri, {
                        viewColumn: vscode.ViewColumn.Active,
                        preview: false,
                    });
                } catch (err: any) {
                    if (err.code === 'FileNotFound') {
                        log(resourceUri.toString());
                        vscode.window.showInformationMessage(`No such file ${resourceUri.path}`);
                    } else {
                        vscode.window.showErrorMessage(err.message);
                    }
                }
            }

            await vscode.commands.executeCommand('revealInExplorer', resourceUri);
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

    if (gitPlatform === 'other') {
        vscode.window.showErrorMessage('Cannot reveal in browser either when using unknown git-platform.');
        return;
    }

    await revealGitResourceInBrowser(
        gitPlatform,
        resource.resourceGroupUrl,
        resource.resourceGroupVersion,
        resource.url,
        log
    );
}

export async function revealGitResourceInBrowser(
    gitPlatform: string,
    resourceGroupUrl: string,
    resourceGroupVersion: string,
    resourceUrl: string,
    log: Function
) {
    let url = '';
    const { host, owner, name } = parseResourceGroupUrl(resourceGroupUrl);

    switch (gitPlatform) {
        case 'gitea':
            // http://localhost:3001/patrik/Evidence/src/commit/6af20806cd962126ec8fcc453b1130881a48a4cf/test_run/data1.dat
            url = [host, owner, name, 'src', 'commit', resourceGroupVersion].join('/') + resourceUrl;
            break;
        case 'gitlab':
            // https://git.isis.vanderbilt.edu/aa-caid/gsn-domain/-/blob/e7df05243d65abb2b63b1d14582f55ca3489cd54/json2gsn/README.md
            url = [host, owner, name, '-', 'blob', resourceGroupVersion].join('/') + resourceUrl;
            break;
        case 'github':
            // https://github.com/webgme/webgme-engine/blob/36bb06687142baba92c414a5975d060bf5c2707f/src/utils.js
            url = [host, owner, name, 'blob', resourceGroupVersion].join('/') + resourceUrl;
        default:
            break;
    }

    const success = await vscode.env.openExternal(vscode.Uri.parse(url));
    log('Opened?', success, url);
}

export async function viewGitResourceDiff(
    gitPlatform: string,
    resource: Resource,
    lastCleanVersion: string,
    log: Function
) {
    let url = '';
    const { host, owner, name } = parseResourceGroupUrl(resource.resourceGroupUrl);

    switch (gitPlatform) {
        case 'gitea':
            // http://localhost:3001/patrik/Evidence/compare/c15794b624..6af20806cd
            url = [host, owner, name, 'compare', `${resource.resourceGroupVersion}..${lastCleanVersion}`].join('/');
            break;
        case 'gitlab':
            // https://git.isis.vanderbilt.edu/aa-caid/depi-impl/-/compare/11ff89d2bd...b6f3eec8fc
            url = [host, owner, name, '-', 'compare', `${resource.resourceGroupVersion}...${lastCleanVersion}`].join(
                '/'
            );
        case 'github':
            // https://github.com/webgme/webgme-engine/compare/36bb066871..2476c23d9b
            url = [host, owner, name, 'compare', `${resource.resourceGroupVersion}..${lastCleanVersion}`].join('/');
        default:
            break;
    }

    const success = await vscode.env.openExternal(vscode.Uri.parse(url));
    log('Opened?', success, url);
}

export async function getGitResourceFromUri(git: GitAPI, uri: vscode.Uri): Promise<Resource> {
    const {
        gitUrl: resourceGroupUrl,
        commitVersion: resourceGroupVersion,
        resourceRelativePath,
    } = await getGitResourceInfoFromPath(git, uri);

    const resourceUrl = `/${resourceRelativePath}`;
    return {
        toolId: 'git',
        resourceGroupName: path.basename(resourceGroupUrl),
        resourceGroupUrl,
        resourceGroupVersion,
        name: path.basename(resourceUrl),
        url: resourceUrl,
        id: resourceUrl,
        deleted: false,
    };
}

export async function tryGetGitUser(
    git: GitAPI,
    uri: vscode.Uri,
    log: Function
): Promise<{ name: string; email: string }> {
    const repo = await tryFindGitRepoForUri(git, uri);
    const result = { name: '', email: '' };

    if (!repo) {
        log('No git repo found for', uri.path);
        return result;
    }

    try {
        result.name = await repo.getConfig('user.name');
        result.email = await repo.getConfig('user.email');
    } catch (err) {
        log('Failed getting user info in local git config', (err as Error).message, 'Trying global config instead..');

        try {
            result.name = await repo.getGlobalConfig('user.name');
            result.email = await repo.getGlobalConfig('user.email');
        } catch (err) {
            log('getGlobalConfig failed to.. Will prompt for username.', (err as Error).message);
        }
    }

    return result;
}

// vscode git-extension commands
// https://github.com/microsoft/vscode/blob/main/extensions/git/src/commands.ts
export async function gitStageAll(repository: Repository) {
    return await vscode.commands.executeCommand('git.stageAll', repository);
}

export async function gitCommit(repository: Repository) {
    return await vscode.commands.executeCommand('git.commit', repository);
}

export async function gitPush(repository: Repository) {
    return await vscode.commands.executeCommand('git.push', repository);
}

export async function gitPushWithTags(repository: Repository) {
    return await vscode.commands.executeCommand('git.pushWithTags', repository);
}
