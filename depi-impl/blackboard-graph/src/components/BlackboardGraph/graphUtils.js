/* eslint-disable no-restricted-syntax */
import { getFullResourceId, getFullResourceGroupId, ABS_PATH_SUFFIX } from '../../utils';

export function expandResources(resources, resourceGroups, atResource) {
    const ids = new Set();
    // console.log('expandResources');
    for (const resource of [...resources].sort((a, b) => a.url.length - b.url.length)) {
        const resourceId = getFullResourceId(resource);
        // console.log('  ', id);

        // We need to make sure are virtual containers are accounted for
        const resourceGroupId = getFullResourceGroupId({ toolId: resource.toolId, url: resource.resourceGroupUrl });
        const resourceGroup = resourceGroups.get(resourceGroupId);
        const { parentRootId, pathPieces } = getParentIds(resource, resourceGroup);

        let parentId = parentRootId;
        let idx = 0;
        for (const pathSegment of pathPieces) {
            const id = `${parentId}${pathSegment}${resourceGroup.pathDivider}`;
            if (!ids.has(id)) {
                ids.add(id);
                atResource({
                    id,
                    parentId: idx > 0 ? parentId : resourceGroupId,
                    resourceGroupId,
                    resource: null,
                    name: pathSegment,
                });
            }

            parentId = id;
            idx += 1;
        }

        if (ids.has(resourceId)) {
            throw new Error(`Resource id ${resourceId} accounted for twice!`);
        }

        // Use original id to account for actual resource.
        ids.add(resourceId);
        atResource({
            id: resourceId,
            parentId: idx > 0 ? parentId : resourceGroupId,
            resourceGroupId,
            resource,
            name: resource.name,
        });
    }
}

/**
 * Gets the parent IDs for a given resource within a specific resource group.
 *
 * @param {object} resource - The resource for which parent IDs are needed.
 * @param {object} resourceGroup - The resource group containing the resource.
 * @returns {ParentsInfo} - An object containing the resource group ID, parent root ID, and an array of path pieces.
 *
 * @typedef {object} ParentsInfo
 * @property {string} resourceGroupId - The ID of the resource group containing the resource.
 * @property {string} parentRootId - The ID of the parent root resource (including path divider).
 * @property {string} pathDivider - The path-divider pf the resource group (e.g. '/').
 * @property {string[]} pathPieces - An array of path pieces representing the resource's parent hierarchy.
 */
export function getParentIds(resource, resourceGroup) {
    const resourceGroupId = getFullResourceGroupId(resourceGroup);
    const { pathDivider } = resourceGroup;
    const pathPieces = resource.url.split(pathDivider);
    const isContainerResource = resource.url.endsWith(pathDivider);
    if (pathPieces[0] === '') {
        pathPieces.shift();
    }

    if (isContainerResource) {
        pathPieces.pop();
    }

    pathPieces.pop();
    return {
        resourceGroupId,
        parentRootId: `${resourceGroupId}${ABS_PATH_SUFFIX}${pathDivider}`,
        pathPieces,
        pathDivider,
    };
}
