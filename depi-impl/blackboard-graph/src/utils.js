/* eslint-disable no-restricted-syntax */
export const ABS_PATH_SUFFIX = '##';
const EDGE_ID_DIVIDER = '--depends-on-->';

export function getFullResourceId({ toolId, resourceGroupUrl, url }) {
    return `${toolId}${ABS_PATH_SUFFIX}${resourceGroupUrl}${ABS_PATH_SUFFIX}${url}`;
}

export function getFullResourceGroupId({ toolId, url }) {
    return `${toolId}${ABS_PATH_SUFFIX}${url}`;
}

export function parseAbsoluteUrl(url) {
    const pieces = url.split(ABS_PATH_SUFFIX);
    if (pieces.length !== 3) {
        throw new Error(`Unparseable url "${url}"`);
    }

    return { toolId: pieces[0], resourceGroupUrl: pieces[1], url: pieces[2] };
}

export function getResourceGroupIdFromId(id) {
    const pieces = id.split(ABS_PATH_SUFFIX);
    if (pieces.length === 2) {
        return id;
    }

    if (pieces.length === 3) {
        return `${pieces[0]}${ABS_PATH_SUFFIX}${pieces[1]}`;
    }

    throw new Error(`Unparseable id "${id}"`);
}

export function getEdgeId(sourceUrl, targetUrl) {
    return `${sourceUrl}${EDGE_ID_DIVIDER}${targetUrl}`;
}

export function parseEdgeId(id) {
    const pieces = id.split(ABS_PATH_SUFFIX);
    if (pieces.length !== 2) {
        throw new Error(`Unparseable edge-id "${id}"`);
    }

    return { sourceUrl: pieces[0], targetUrl: pieces[1] };
}

export function getShortDisplayVersion(version) {
    return version.startsWith('#') ? version.substring(0, 9) : `#${version.substring(0, 8)}`;
}

export function getResourceRefFromResource(resource, resourceGroups) {
    const resourceGroup = resourceGroups.find((rg) => rg.url === resource.resourceGroupUrl);

    if (!resourceGroup) {
        throw new Error('Missing resource group: ', resource.resourceGroupUrl);
    }

    return {
        ...resource,
        toolId: resourceGroup.toolId,
        resourceGroupName: resourceGroup.name,
        resourceGroupVersion: resourceGroup.version,
    };
}

export const isSameResourceGroup = (rg1, rg2) => rg1 && rg2 && rg1.toolId === rg2.toolId && rg1.url === rg2.url;

export const isSameResource = (r1, r2) =>
    r1 && r2 && r1.toolId === r2.toolId && r1.url === r2.url && r1.resourceGroupUrl === r2.resourceGroupUrl;

export const isSameLink = (l1, l2) =>
    l1 &&
    l2 &&
    l1.source &&
    l2.source &&
    l1.target &&
    l2.target &&
    isSameResource(l1.source, l2.source) &&
    isSameResource(l1.target, l2.target);

export function removeEntriesByMutation(resources, links, removedEntries) {
    removedEntries.forEach((entry) => {
        const isLink = entry.source && entry.target;

        if (isLink) {
            const idx = links.findIndex((l) => isSameLink(l, entry));
            if (idx > -1) {
                links.splice(idx, 1);
            }
        } else {
            const idx = resources.findIndex((r) => isSameResource(r, entry));
            if (idx > -1) {
                resources.splice(idx, 1);
            }
        }
    });
}

export function getAdditionalLooseLinks(links, removedResources, removedLinks) {
    const result = [];
    removedResources.forEach((resource) => {
        links
            .filter(
                (l) =>
                    (isSameResource(l.source, resource) || isSameResource(l.target, resource)) &&
                    !removedLinks.some((removedLink) => isSameLink(removedLink, l))
            )
            .forEach((looseLink) => {
                result.push(looseLink);
            });
    });

    return result;
}

export function getUpdatedSelection(selection, dependencyGraph, depiModel, blackboardModel) {
    const newSelection = [];

    for (const { isLink, isResourceGroup, entry } of selection) {
        let bbEntry = null;
        let depiEntry = null;

        if (dependencyGraph.resource) {
            // We're in dep-graph-mode (or switching to it).
            if (isResourceGroup) {
                // Do not select resource-groups in this mode.
                depiEntry = null;
            } else if (isLink) {
                depiEntry = dependencyGraph.links.find((link) => isSameLink(link, entry));
            } else {
                for (const { source, target } of dependencyGraph.links) {
                    if (isSameResource(source, entry)) {
                        depiEntry = source;
                        break;
                    }
                    if (isSameResource(target, entry)) {
                        depiEntry = target;
                        break;
                    }
                }
            }
        } else if (!dependencyGraph.resource) {
            // We're in blackboard-mode (or switching to it).
            if (isResourceGroup) {
                depiEntry = depiModel.resourceGroups.find((rg) => isSameResourceGroup(rg, entry));
                if (!depiEntry) {
                    bbEntry = blackboardModel.resources
                        .map(({ toolId, resourceGroupUrl }) => ({
                            toolId,
                            url: resourceGroupUrl,
                        }))
                        .find((rg) => isSameResourceGroup(rg, entry));
                }
            } else if (isLink) {
                depiEntry = depiModel.links.find((link) => isSameLink(link, entry));
                bbEntry = blackboardModel.links.find((link) => isSameLink(link, entry));
            } else {
                depiEntry = depiModel.resources.find((resource) => isSameResource(resource, entry));
                bbEntry = blackboardModel.resources.find((resource) => isSameResource(resource, entry));
            }
        }

        if (bbEntry || depiEntry) {
            newSelection.push({
                isResourceGroup,
                isLink,
                inDepi: Boolean(depiEntry),
                onBlackboard: Boolean(bbEntry),
                entry: depiEntry || bbEntry,
            });
        }
    }

    console.log('New selection length:', newSelection.length);
    return newSelection;
}
