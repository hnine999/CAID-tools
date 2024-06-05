/* eslint-disable no-restricted-syntax */
import { dependencyGraphMock, dependantsGraphMock } from './mocks/dependencyGraphMock';
import { depiModelMock } from './mocks/depiModelMock';
import { EVENT_TYPES } from '../EVENT_TYPES';
import { isSameLink, isSameResource, isSameResourceGroup, removeEntriesByMutation } from '../utils';

const blackboardModelMock = {
    resources: [
        {
            toolId: 'git',
            resourceGroupName: 'BB.git',
            resourceGroupUrl: 'http://localhost:3001/patrik/BlackboardOnly.git',
            resourceGroupVersion: '1234fcf89d045188d98d6268d1213532075aca6a',
            name: 'bb.zip',
            url: '/folder/bb.zip',
            id: '/folder/bb.zip',
            deleted: false,
        },
        {
            toolId: 'git',
            resourceGroupName: 'BB.git',
            resourceGroupUrl: 'http://localhost:3001/patrik/BlackboardOnly.git',
            resourceGroupVersion: '1234fcf89d045188d98d6268d1213532075aca6a',
            name: 'folder',
            url: '/folder/',
            id: '/folder/',
            deleted: false,
        },
        {
            toolId: 'git',
            resourceGroupName: 'c-sources.git',
            resourceGroupUrl: 'http://localhost:3001/patrik/c-sources.git',
            resourceGroupVersion: '6d345396ac27cb7e1af5ff9d94d6e02600805363',
            name: 'alibabba.py',
            url: '/folder/subFolder/subSubFolder/subSubSubFolder/alibabba.py',
            id: '/folder/subFolder/subSubFolder/subSubSubFolder/alibabba.py',
            labels: ['ROSComponent'],
            deleted: false,
        },
    ],
    links: [],
};

const toolsConfigs = {
    git: {
        pathSeparator: '/',
        labels: ['Artifact', 'ROSComponent', 'SourceFile'],
    },
};

export default class DepiApi {
    constructor(vscode, eventHandler) {
        this.vscode = vscode;
        this.eventHandler = eventHandler;
        if (!vscode) {
            this.mockState = {
                depiModel: depiModelMock,
                blackboardModel: blackboardModelMock,
                dependencyGraph: dependencyGraphMock,
            };
            return;
        }

        window.addEventListener('message', ({ data }) => {
            if (data) {
                eventHandler(data);
            } else {
                console.error('Unknown message - no data provided');
            }
        });
    }

    requestBranchesAndTags = () => {
        if (this.vscode) {
            this.vscode.postMessage({
                type: EVENT_TYPES.REQUEST_BRANCHES_AND_TAGS,
            });
            return;
        }

        setTimeout(() => {
            this.eventHandler({
                type: EVENT_TYPES.BRANCHES_AND_TAGS,
                value: { branches: ['main', 'v1.0.0'], tags: ['v0.1.0', 'v0.2.0'] },
            });
        });
    };

    requestDepiModel = (branchName) => {
        if (this.vscode) {
            this.vscode.postMessage({
                type: EVENT_TYPES.REQUEST_DEPI_MODEL,
                value: { branchName },
            });
            return;
        }

        setTimeout(() => {
            this.eventHandler({
                type: EVENT_TYPES.DEPI_MODEL,
                value: this.mockState.depiModel,
            });
        });
    };

    expandResourceGroups = (resourceGroupRefs) => {
        if (this.vscode) {
            this.vscode.postMessage({
                type: EVENT_TYPES.EXPAND_RESOURCE_GROUPS,
                value: resourceGroupRefs,
            });
            return;
        }

        setTimeout(() => {
            const depiModel = { ...this.mockState.depiModel };
            depiModel.resourceGroups = depiModel.resourceGroups.map((rg) => {
                if (resourceGroupRefs.some((rgRef) => isSameResourceGroup(rgRef, rg))) {
                    const newRg = { ...rg };
                    newRg.isActiveInEditor = true;
                    return newRg;
                }

                return rg;
            });

            depiModel.expandState += 1;
            this.mockState.depiModel = depiModel;
            this.eventHandler({
                type: EVENT_TYPES.DEPI_MODEL,
                value: this.mockState.depiModel,
            });
        });
    };

    collapseResourceGroups = (resourceGroupRefs) => {
        if (this.vscode) {
            this.vscode.postMessage({
                type: EVENT_TYPES.COLLAPSE_RESOURCE_GROUPS,
                value: resourceGroupRefs,
            });
            return;
        }

        setTimeout(() => {
            const depiModel = { ...this.mockState.depiModel };
            depiModel.resourceGroups = depiModel.resourceGroups.map((rg) => {
                if (resourceGroupRefs.some((rgRef) => isSameResourceGroup(rgRef, rg))) {
                    const newRg = { ...rg };
                    newRg.isActiveInEditor = false;
                    return newRg;
                }

                return rg;
            });

            this.mockState.depiModel = depiModel;
            this.eventHandler({
                type: EVENT_TYPES.DEPI_MODEL,
                value: this.mockState.depiModel,
            });
        });
    };

    requestBlackboard = () => {
        if (this.vscode) {
            this.vscode.postMessage({
                type: EVENT_TYPES.REQUEST_BLACKBOARD_MODEL,
            });
            return;
        }

        setTimeout(() => {
            this.eventHandler({
                type: EVENT_TYPES.BLACKBOARD_MODEL,
                value: this.mockState.blackboardModel,
            });
        });
    };

    requestDependencyGraph = (resource, branchName, dependants) => {
        if (this.vscode) {
            this.vscode.postMessage({
                type: EVENT_TYPES.REQUEST_DEPENDENCY_GRAPH,
                value: { resource, branchName, dependants },
            });
            return;
        }

        setTimeout(() => {
            this.eventHandler({
                type: EVENT_TYPES.DEPENDENCY_GRAPH,
                value: dependants ? dependantsGraphMock : dependencyGraphMock,
            });
        });
    };

    requestToolsConfig = () => {
        if (this.vscode) {
            this.vscode.postMessage({
                type: EVENT_TYPES.REQUEST_TOOLS_CONFIG,
            });
            return;
        }

        setTimeout(() => {
            this.eventHandler({
                type: EVENT_TYPES.TOOLS_CONFIG,
                value: toolsConfigs,
            });
        });
    };

    linkResources = (source, target) => {
        if (this.vscode) {
            this.vscode.postMessage({
                type: EVENT_TYPES.LINK_RESOURCES,
                value: { source, target },
            });
            return;
        }

        for (const link of this.mockState.blackboardModel.links) {
            if (isSameResource(link.source, source) && isSameResource(link.target, source)) {
                return;
            }
        }

        const blackboardModel = { ...this.mockState.blackboardModel };
        blackboardModel.links = [
            ...blackboardModel.links,
            { source, target, dirty: false, lastCleanVersion: source.resourceGroupVersion, inferredDirtiness: [] },
        ];
        let hasSource = false;
        let hasTarget = false;

        for (const resource of blackboardModel.resources) {
            if (isSameResource(resource, source)) {
                hasSource = true;
            } else if (isSameResource(resource, target)) {
                hasTarget = true;
            }
        }

        if (!hasSource || !hasTarget) {
            blackboardModel.resources = [...blackboardModel.resources];
            if (!hasSource) blackboardModel.resources.push(source);
            if (!hasTarget) blackboardModel.resources.push(target);
        }

        setTimeout(() => {
            this.mockState.blackboardModel = blackboardModel;
            this.eventHandler({
                type: EVENT_TYPES.BLACKBOARD_MODEL,
                value: this.mockState.blackboardModel,
            });
        });
    };

    saveBlackboard = () => {
        if (this.vscode) {
            this.vscode.postMessage({
                type: EVENT_TYPES.SAVE_BLACKBOARD,
            });
            return;
        }

        const { resources, links } = this.mockState.blackboardModel;
        this.mockState.depiModel = { ...this.mockState.depiModel };

        this.mockState.depiModel.resourceGroups = [...this.mockState.depiModel.resourceGroups];
        this.mockState.depiModel.resources = [...this.mockState.depiModel.resources];
        resources.forEach((resource) => {
            if (!this.mockState.depiModel.resources.some((r) => isSameResource(r, resource))) {
                this.mockState.depiModel.resources.push(resource);
            }

            if (!this.mockState.depiModel.resourceGroups.some((rg) => rg.url === resource.resourceGroupUrl)) {
                this.mockState.depiModel.resourceGroups.push({
                    url: resource.resourceGroupUrl,
                    toolId: resource.toolId,
                    name: resource.resourceGroupName,
                    version: resource.resourceGroupVersion,
                    isActiveInEditor: true,
                    pathDivider: '/',
                });
            }
        });

        this.mockState.depiModel.links = [...this.mockState.depiModel.links, ...links];
        this.mockState.blackboardModel = { resources: [], links: [] };

        setTimeout(() => {
            this.eventHandler({
                type: EVENT_TYPES.DEPI_MODEL,
                value: this.mockState.depiModel,
            });
        });

        setTimeout(() => {
            this.eventHandler({
                type: EVENT_TYPES.BLACKBOARD_MODEL,
                value: this.mockState.blackboardModel,
            });
        });
    };

    clearBlackboard = () => {
        if (this.vscode) {
            this.vscode.postMessage({
                type: EVENT_TYPES.CLEAR_BLACKBOARD,
            });
            return;
        }

        setTimeout(() => {
            this.mockState.blackboardModel = { resources: [], links: [] };
            this.eventHandler({
                type: EVENT_TYPES.BLACKBOARD_MODEL,
                value: this.mockState.blackboardModel,
            });
        });
    };

    removeEntriesFromBlackboard = (entries) => {
        if (this.vscode) {
            this.vscode.postMessage({
                type: EVENT_TYPES.REMOVE_ENTRIES_FROM_BLACKBOARD,
                value: splitLinksAndResources(entries),
            });
            return;
        }

        this.mockState.blackboardModel = { ...this.mockState.blackboardModel };
        this.mockState.blackboardModel.resources = [...this.mockState.blackboardModel.resources];
        this.mockState.blackboardModel.links = [...this.mockState.blackboardModel.links];

        removeEntriesByMutation(
            this.mockState.blackboardModel.resources,
            this.mockState.blackboardModel.links,
            entries
        );

        setTimeout(() => {
            this.eventHandler({
                type: EVENT_TYPES.BLACKBOARD_MODEL,
                value: this.mockState.blackboardModel,
            });
        });
    };

    deleteEntriesFromDepi = (entries) => {
        if (this.vscode) {
            this.vscode.postMessage({
                type: EVENT_TYPES.DELETE_ENTRIES_FROM_DEPI,
                value: splitLinksAndResources(entries),
            });
            return;
        }

        this.mockState.depiModel = { ...this.mockState.depiModel };
        this.mockState.depiModel.resources = [...this.mockState.depiModel.resources];
        this.mockState.depiModel.links = [...this.mockState.depiModel.links];

        removeEntriesByMutation(this.mockState.depiModel.resources, this.mockState.depiModel.links, entries);

        setTimeout(() => {
            this.eventHandler({
                type: EVENT_TYPES.DEPI_MODEL,
                value: this.mockState.depiModel,
            });
        });
    };

    markLinksClean = (links, propagate) => {
        if (this.vscode) {
            this.vscode.postMessage({
                type: EVENT_TYPES.MARK_LINKS_CLEAN,
                value: { links, propagate },
            });
            return;
        }

        this.mockState.depiModel = { ...this.mockState.depiModel };

        this.mockState.depiModel.links = this.mockState.depiModel.links.map((link) => {
            if (links.some((cleanUpLink) => isSameLink(cleanUpLink, link))) {
                const newLink = { ...link };
                newLink.dirty = false;
                return newLink;
            }

            return link;
        });

        setTimeout(() => {
            this.eventHandler({
                type: EVENT_TYPES.DEPI_MODEL,
                value: this.mockState.depiModel,
            });
        });
    };

    markInferredDirtinessClean = (link, dirtinessSource, propagate) => {
        if (this.vscode) {
            this.vscode.postMessage({
                type: EVENT_TYPES.MARK_INFERRED_DIRTINESS_CLEAN,
                value: { link, dirtinessSource, propagate },
            });
            return;
        }

        this.mockState.depiModel = { ...this.mockState.depiModel };

        this.mockState.depiModel.links = this.mockState.depiModel.links.map((cleanUpLink) => {
            if (isSameLink(cleanUpLink, link)) {
                const newLink = { ...cleanUpLink };
                newLink.inferredDirtiness = newLink.inferredDirtiness.filter((res) =>
                    isSameResource(res, dirtinessSource)
                );
                return newLink;
            }

            return cleanUpLink;
        });

        setTimeout(() => {
            this.eventHandler({
                type: EVENT_TYPES.DEPI_MODEL,
                value: this.mockState.depiModel,
            });
        });
    };

    markAllClean = (links) => {
        if (this.vscode) {
            this.vscode.postMessage({
                type: EVENT_TYPES.MARK_ALL_CLEAN,
                value: { links },
            });
            return;
        }

        this.mockState.depiModel = { ...this.mockState.depiModel };

        this.mockState.depiModel.links = this.mockState.depiModel.links.map((link) => {
            if (links.some((cleanUpLink) => isSameLink(cleanUpLink, link))) {
                const newLink = { ...link };
                newLink.dirty = false;
                newLink.inferredDirtiness = [];
                return newLink;
            }

            return link;
        });

        setTimeout(() => {
            this.eventHandler({
                type: EVENT_TYPES.DEPI_MODEL,
                value: this.mockState.depiModel,
            });
        });
    };

    revealInEditor = (resource) => {
        if (this.vscode) {
            this.vscode.postMessage({
                type: EVENT_TYPES.REVEAL_IN_EDITOR,
                value: resource,
            });
            return;
        }

        alert(JSON.stringify(resource));
    };

    editResourceGroup = (resourceGroupRef, updateDesc, remove) => {
        if (this.vscode) {
            this.vscode.postMessage({
                type: EVENT_TYPES.EDIT_RESOURCE_GROUP,
                value: { resourceGroupRef, updateDesc, remove },
            });
            return;
        }

        function getUpdatedResource(resource) {
            if (!isSameResourceGroup({ toolId: resource.toolId, url: resource.resourceGroupUrl }, resourceGroupRef)) {
                return resource;
            }

            return {
                ...resource,
                toolId: updateDesc.toolId,
                resourceGroupUrl: updateDesc.url,
                resourceGroupVersion: updateDesc.version,
            };
        }

        this.mockState.depiModel = { ...this.mockState.depiModel };

        if (remove) {
            this.mockState.depiModel.resourceGroups = this.mockState.depiModel.resourceGroups.filter(
                (rg) => !isSameResourceGroup(rg, resourceGroupRef)
            );
            this.mockState.depiModel.resources = this.mockState.depiModel.resources.filter(
                ({ resourceGroupUrl, toolId }) =>
                    !isSameResourceGroup({ toolId, url: resourceGroupUrl }, resourceGroupRef)
            );

            this.mockState.depiModel.links = this.mockState.depiModel.links.filter(
                ({ source, target }) =>
                    !isSameResourceGroup({ toolId: source.toolId, url: source.resourceGroupUrl }, resourceGroupRef) &&
                    !isSameResourceGroup({ toolId: target.toolId, url: target.resourceGroupUrl }, resourceGroupRef)
            );
        } else {
            this.mockState.depiModel.resourceGroups = this.mockState.depiModel.resourceGroups.map((rg) => {
                if (!isSameResourceGroup(rg, resourceGroupRef)) {
                    return rg;
                }

                return {
                    ...updateDesc,
                    // Non-updateables
                    pathDivider: rg.pathDivider,
                    isActiveInEditor: rg.isActiveInEditor,
                };
            });

            this.mockState.depiModel.resources = this.mockState.depiModel.resources.map(getUpdatedResource);
            this.mockState.depiModel.links = this.mockState.depiModel.links.map((link) => ({
                ...link,
                inferredDirtiness: [], // TODO: This is just a mock though..
                source: getUpdatedResource(link.source),
                target: getUpdatedResource(link.target),
            }));
        }

        setTimeout(() => {
            this.eventHandler({
                type: EVENT_TYPES.DEPI_MODEL,
                value: this.mockState.depiModel,
            });
        });
    };

    viewResourceDiff = (resource, lastCleanVersion) => {
        if (this.vscode) {
            this.vscode.postMessage({
                type: EVENT_TYPES.VIEW_RESOURCE_DIFF,
                value: { resource, lastCleanVersion },
            });
            return;
        }

        alert(JSON.stringify({ resource, lastCleanVersion }));
    };
}

const splitLinksAndResources = (entries) => {
    const links = [];
    const resources = [];
    for (const entry of entries) {
        if (entry.source && entry.target) {
            links.push(entry);
        }

        resources.push(entry);
    }

    return { links, resources };
};
