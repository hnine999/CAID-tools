import * as path from 'path';
import * as vscode from 'vscode';
import { depiUtils, Resource, ResourceGroup, ResourceLink, DepiSession } from 'depi-node-client';

import { API as GitAPI } from './@types/git';
import { getGitResourceInfoFromPath, parseResourceGroupUrl } from './gitUtils';
import DepiExtensionApi from './depiExtensionApi';
import CONSTANTS from './CONSTANTS';

/**
 * Methods and state wrt to depi integration.
 * One instance is created and kept alive as long as the panel is.
 * During model-context switch - the dirUri needs to be updated.
 * 
 * This instance is destroyed when the panel is and a new instance created whenever a new panel is brought up.
 */
export default class GsnDepi {
    log: Function;
    git: GitAPI;
    dirUri: vscode.Uri;
    depiExtApi: DepiExtensionApi;
    depiWatcherId: string;
    pingIntervalId: NodeJS.Timer;

    constructor(git: GitAPI, dirUri: vscode.Uri, log: Function) {
        this.git = git;
        this.dirUri = dirUri;
        this.log = log;
        this.depiExtApi = new DepiExtensionApi(log);
    }

    _resolveResourceGroup = async (depiSession: DepiSession):
        Promise<{ resourceGroup: ResourceGroup, remoteVersion: string }> => {
        const { gitUrl, commitVersion, resourceRelativePath }
            = await getGitResourceInfoFromPath(this.git, this.dirUri);

        const newRGProps = parseResourceGroupUrl(gitUrl);
        let url = '';
        let resourceGroupName = '';
        let remoteVersion = '';

        // Try to find matching resource-group based on
        for (const resourceGroup of await depiUtils.getResourceGroups(depiSession as DepiSession)) {
            if (resourceGroup.toolId !== 'git-gsn') {
                continue;
            }

            const { host, owner, name } = parseResourceGroupUrl(resourceGroup.url.split(CONSTANTS.DEPI.GIT_URL_END_CHAR)[0]);
            if (owner === newRGProps.owner && name === newRGProps.name) {
                this.log('Found matching resource-group', resourceGroup.url, 'for', owner, '/', name);
                url = resourceGroup.url;
                resourceGroupName = resourceGroup.name;
                remoteVersion = resourceGroup.version;
                break;
            }
        }

        if (!url) {
            url = `${gitUrl}${CONSTANTS.DEPI.GIT_URL_END_CHAR}${resourceRelativePath}`;
            resourceGroupName = path.basename(this.dirUri.fsPath);
        }

        return {
            resourceGroup: {
                toolId: CONSTANTS.DEPI.TOOL_ID,
                url,
                name: resourceGroupName,
                version: commitVersion,
                pathDivider: CONSTANTS.DEPI.PATH_DIVIDER,
                isActiveInEditor: true,
            },
            remoteVersion
        }
    }

    _resolveResource = async (depiSession: DepiSession, { nodeId, uuid }: { nodeId: string, uuid: string }): Promise<Resource> => {
        const { resourceGroup } = await this._resolveResourceGroup(depiSession);
        const resourceName = path.basename(nodeId);

        return {
            toolId: CONSTANTS.DEPI.TOOL_ID,
            resourceGroupName: resourceGroup.name,
            resourceGroupUrl: resourceGroup.url,
            resourceGroupVersion: resourceGroup.version,
            id: uuid,
            name: resourceName,
            url: `${resourceGroup.pathDivider}${nodeId}`,
            deleted: false,
        };
    }

    _getIsDirtyAndEvidence = ({ resource, links }: { resource: Resource, links: ResourceLink[] }): { isDirty: boolean, evidence: Resource[] } => {
        let isDirty = false;
        const evidence: Resource[] = [];
        links.forEach((link) => {
            isDirty = isDirty || link.dirty || link.inferredDirtiness.length > 0;
            if (link.source &&
                link.source.resourceGroupUrl === resource.resourceGroupUrl &&
                link.source.url === resource.url) {
                evidence.push(link.target);
            }
        });

        return { isDirty, evidence };
    }

    updateModelDir = (dirUri: vscode.Uri) => {
        this.log('Updating dirUri for GsnDepi');
        this.dirUri = dirUri;
    }

    switchToBranch = async (branchName: string) => {
        const depiSession = await this.depiExtApi.getDepiSession();
        if (depiSession.branchName !== branchName) {
            this.log(`Setting depi branch to tag ${branchName}!`);
            // FIXME: Better error handling!
            const branch = await depiUtils.setBranch(depiSession, branchName);
            if (!branch) {
                this.log(`Depi branch did not exist will create it..`);
                await depiUtils.createBranch(depiSession, branchName, 'main');
            }

            depiSession.branchName = await depiUtils.setBranch(depiSession, branchName);
        } else {
            this.log('_switchToBranch: branch was already selected', branchName);
        }

        return depiSession;
    }

    convertBranchToTag = async (branchName: string) => {
        const depiSession = await this.switchToBranch('main');

        await depiUtils.createTag(depiSession, branchName, branchName);
        // await depiUtils.deleteBranch(depiSession, branchName);
    }

    deleteBranch = async (branchName: string) => {
        const depiSession = await this.switchToBranch('main');
        vscode.window.showInformationMessage('TODO: Add support to remove branch from depi.')
        // await depiUtils.deleteBranch(depiSession, branchName);
    }

    getResourceGroup = async (): Promise<ResourceGroup> => {
        const depiSession = await this.depiExtApi.getDepiSession();
        const { resourceGroup, remoteVersion } = await this._resolveResourceGroup(depiSession);
        if (!remoteVersion) {
            return null;
        }

        resourceGroup.version = remoteVersion;
        return resourceGroup;
    }

    getAllResources = async () => {
        const depiSession = await this.depiExtApi.getDepiSession();
        const { resourceGroup } = await this._resolveResourceGroup(depiSession);
        const resourcePattern = {
            toolId: CONSTANTS.DEPI.TOOL_ID,
            resourceGroupName: resourceGroup.name,
            resourceGroupUrl: resourceGroup.url,
            urlPattern: '.*'
        };

        const resources = await depiUtils.getResources(depiSession, [resourcePattern])

        const res = {};
        for (const resource of resources) {
            const depGraph = await depiUtils.getDependencies(depiSession, resource);
            if (!depGraph.resource) {
                continue;
            }

            const { isDirty, evidence } = this._getIsDirtyAndEvidence(depGraph);
            let status = CONSTANTS.NODE_DEPI_STATES.RESOURCE_UP_TO_DATE;

            if (evidence.length === 0) {
                status = CONSTANTS.NODE_DEPI_STATES.NO_LINKED_EVIDENCE;
            } else if (isDirty) {
                status = CONSTANTS.NODE_DEPI_STATES.RESOURCE_DIRTY;
            }

            res[resource.id] = { status, evidence };
        }

        return res;
    }

    getEvidenceInfo = async ({ nodeId, uuid }: { nodeId: string, uuid: string }) => {
        let depiSession: DepiSession;
        const result = {
            status: CONSTANTS.NODE_DEPI_STATES.NO_DEPI_RESOURCE,
            evidence: []
        };

        try {
            depiSession = await this.depiExtApi.getDepiSession();
        } catch {
            result.status = CONSTANTS.NODE_DEPI_STATES.DEPI_UNAVAILABLE;
            return result;
        }

        const resource = await this._resolveResource(depiSession, { nodeId, uuid });

        let depGraph = await depiUtils.getDependencies(depiSession, resource);

        if (!depGraph.resource) {
            return result;
        }

        const { isDirty, evidence } = this._getIsDirtyAndEvidence(depGraph);
        result.status = CONSTANTS.NODE_DEPI_STATES.RESOURCE_UP_TO_DATE;
        result.evidence = evidence;

        if (evidence.length === 0) {
            result.status = CONSTANTS.NODE_DEPI_STATES.NO_LINKED_EVIDENCE;
        } else if (isDirty) {
            result.status = CONSTANTS.NODE_DEPI_STATES.RESOURCE_DIRTY;
        }

        return result;
    }

    addAsResource = async ({ nodeId, uuid }: { nodeId: string, uuid: string }) => {
        const depiSession = await this.depiExtApi.getDepiSession();

        const resource = await this._resolveResource(depiSession, { nodeId, uuid });

        const selectedOption = await vscode.window.showInformationMessage(
            'Would you like to select an existing resource in Depi as a dependency now?',
            { modal: true },
            'Yes',
            'No - I will link to it using the Depi Blackboard'
        );

        await depiUtils.addResourcesToBlackboard(depiSession as DepiSession, [resource]);

        if (selectedOption === 'Yes') {
            const targetResource = await this.depiExtApi.selectDepiResource();
            if (targetResource) {
                await depiUtils.addResourcesToBlackboard(depiSession as DepiSession, [targetResource]);
                await depiUtils.addLinkToBlackboard(depiSession as DepiSession, resource, targetResource);
            }
        } else {
            await depiUtils.addResourcesToBlackboard(depiSession, [resource]);
        }

        await this.depiExtApi.showBlackboard();
    }

    removeAsResouce = async ({ nodeId, uuid }: { nodeId: string, uuid: string }) => {
        const depiSession = await this.depiExtApi.getDepiSession();
        const resource = await this._resolveResource(depiSession, { nodeId, uuid });

        const { links } = await depiUtils.getDependencies(depiSession, resource);

        const linksToRemove = links.filter((link) =>
            link.target && link.source &&
            link.source.toolId === resource.toolId &&
            link.source.resourceGroupUrl === resource.resourceGroupUrl &&
            link.source.url === resource.url);

        await depiUtils.deleteEntriesFromDepi(depiSession, { links: linksToRemove, resources: [resource] })
    }

    showDependencyGraph = async ({ nodeId, uuid }: { nodeId: string, uuid: string }) => {
        const depiSession = await this.depiExtApi.getDepiSession();
        const resource = await this._resolveResource(depiSession, { nodeId, uuid });
        await this.depiExtApi.showDependencyGraph(resource);
    }

    linkEvidence = this.addAsResource;

    unlinkEvidence = async ({ nodeId, uuid, evidence }: { nodeId: string, uuid: string, evidence: Resource }) => {
        const depiSession = await this.depiExtApi.getDepiSession();
        const resource = await this._resolveResource(depiSession, { nodeId, uuid });

        const { links } = await depiUtils.getDependencies(depiSession, resource);

        const linksToRemove = links.filter((link) =>
            depiUtils.isSameResource(link.source, resource) &&
            depiUtils.isSameResource(link.target, evidence)
        );

        await depiUtils.deleteEntriesFromDepi(depiSession, { links: linksToRemove, resources: [] })
    }

    revealEvidence = async (resource: Resource) => await this.depiExtApi.revealDepiResource(resource);

    addDepiWatcher = async (onUpdate: Function) => {
        const depiSession = await this.depiExtApi.getDepiSession();
        this.depiWatcherId = await depiUtils.watchDepi(depiSession, () => { onUpdate() }, (err) => { this.log(err) });

        const config = vscode.workspace.getConfiguration('gsnGraph');
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

    destroy = async () => {
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