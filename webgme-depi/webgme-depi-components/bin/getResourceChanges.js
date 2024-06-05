const CHANGE_TYPE = {
    Added: 0,
    Modified: 1,
    Renamed: 2,
    Removed: 3,
}

/**
 * 
 * @param {Resource[]} resources 
 * @param {GmeClasses.Core} core 
 * @param {GmeClasses.Core.Node} oldRoot 
 * @param {GmeClasses.Core.Node} newRoot
 * 
 * @returns {Promise<ResourceChange[]>}
 */
async function getResourceChanges(resources, core, oldRoot, newRoot) {
    const result = [];
    for (const resource of resources) {
        const change = await getResourceChange(resource, core, oldRoot, newRoot);
        if (change) {
            result.push(change);
        }
    }

    return result;
}

/**
 * 
 * @param {Resource} resource
 * @param {GmeClasses.Core} core 
 * @param {GmeClasses.Core.Node} oldRoot 
 * @param {GmeClasses.Core.Node} newRoot
 * 
 * @returns {Promise<ResourceChange|null>}
 */
async function getResourceChange(resource, core, oldRoot, newRoot) {
    const { url, id: guid } = resource;
    let path = url.endsWith('/') ? url.substring(0, url.length - 1) : url;

    const oldNode = await core.loadByPath(oldRoot, path);
    const newNode = await core.loadByPath(newRoot, path);
    if (!newNode) {
        return await getMovedOrDeletedResourceChange(resource, core, oldNode, newRoot);
    }

    if (core.getGuid(newNode) !== guid) {
        // The nodes have been moved around and the node at the path in the new state is not the same node.
        return await getMovedOrDeletedResourceChange(resource, core, oldNode, newRoot);
    }

    if (await wasNodeModified(core, oldNode, newNode)) {
        return {
            changeType: CHANGE_TYPE.Modified,
            name: resource.name,
            url: resource.url,
            id: resource.id,
            newName: core.getAttribute(newNode, 'name'),
            newUrl: resource.url,
            newId: resource.id,
        };
    }

    return null;
}

/**
 * 
 * @param {Resource} resource
 * @param {GmeClasses.Core} core 
 * @param {GmeClasses.Core.Node} oldNode
 * @param {GmeClasses.Core.Node} newRoot
 * 
 * @returns {Promise<ResourceChange>}
 */
async function getMovedOrDeletedResourceChange(resource, core, oldNode, newRoot) {
    const { id: guid } = resource;
    let result = null;

    const getRemovedChange = () => ({
        changeType: CHANGE_TYPE.Removed,
        name: resource.name,
        url: resource.url,
        id: resource.id,
        newName: '',
        newUrl: '',
        newId: '',
    });

    const getModifiedChange = (node) => ({
        changeType: CHANGE_TYPE.Modified,
        name: resource.name,
        url: resource.url,
        id: resource.id,
        newName: core.getAttribute(node, 'name'),
        newUrl: resource.url.endsWith('/') ? `${core.getPath(node)}/` : core.getPath(node),
        newId: resource.id,
    });

    console.log('Node was either moved or deleted', resource.name, resource.url, resource.id);

    const oldBase = core.getBase(oldNode);
    if (oldBase) {
        const newBase = await core.loadByPath(newRoot, core.getPath(oldBase));
        if (newBase && core.getGuid(newBase) === core.getGuid(oldBase)) {
            console.log('Same base node found in new tree - checking direct instances');
            for (const instanceNode of await core.loadInstances(newBase)) {
                if (core.getGuid(instanceNode) === guid) {
                    return getModifiedChange(instanceNode);
                }
            }

            return getRemovedChange();
        }
    }

    console.log('Could not match direct base node - will traverse composition tree.');

    // N.B. This is a depth-first search from the root-node.
    async function traverseTree(node) {
        if (core.getGuid(node) === guid) {
            // We found the node! These all count as modifed.
            result = getModifiedChange(node);
        }

        if (result) { return; }

        for (const childNode of core.loadChildren(node)) {
            if (result) { return; }
            await traverseTree(childNode);
        }
    };

    await traverseTree(newRoot);

    return result || getRemovedChange();
}

/**
 * @param {GmeClasses.Core} core 
 * @param {GmeClasses.Core.Node} oldNode
 * @param {GmeClasses.Core.Node} newNode
 * 
 * @returns {Promise<boolean>}
 */
async function wasNodeModified(core, oldNode, newNode) {
    return !await nodeAndChildrenSameRec(core, core.getPath(oldNode), oldNode, newNode);
}

/**
 * @param {GmeClasses.Core} core 
 * @param {string} resourceNodePath
 * @param {GmeClasses.Core.Node} oldNode
 * @param {GmeClasses.Core.Node} newNode
 * 
 * @returns {Promise<boolean>}
 */
async function nodeAndChildrenSameRec(core, resourceNodePath, oldNode, newNode) {
    // First check the nodes themselves
    const nodesTheSame = await propertiesAndRelationshipsSame(core, resourceNodePath, oldNode, newNode);

    if (!nodesTheSame) {
        return false;
    }

    const oldChildren = await core.loadChildren(oldNode);
    const newChildren = await core.loadChildren(newNode);

    if (oldChildren.length !== newChildren.length) {
        return false;
    }

    const guidToNewChildren = new Map(newChildren.map(node => [core.getGuid(node), node]));

    // Store children in the first iteration and avoid recursion if children aren't even the same.
    const nodePairs = []; // [[oldChild_1, newChild_1], ..., [oldChild_n, newChild_n]]

    for (const oldChild of oldChildren) {
        const oldGuid = core.getGuid(oldChild);
        if (!guidToNewChildren.has(oldGuid)) {
            return false;
        }

        nodePairs.push([oldChild, guidToNewChildren.get(oldGuid)]);
    }

    for (const [oldChild, newChild] of nodePairs) {
        if (!await nodeAndChildrenSameRec(core, resourceNodePath, oldChild, newChild)) {
            return false;
        }
    }

    return true;
}

/**
 * Alternative approach to check if nodes have changed. Goes thru the inheritance chain and checks if
 * the hashes are the same. This would be much faster (and less complex and error prone), but
 * would not discriminate between registry changes and would only account for internal relations.
 * 
 * @param {GmeClasses.Core} core 
 * @param {GmeClasses.Core.Node} oldNode
 * @param {GmeClasses.Core.Node} newNode
 * 
 * @returns {boolean}
 */
function hashesSame(core, oldNode, newNode) {

    let oldBaseNode = oldNode;
    let newBaseNode = newNode;

    while (oldBaseNode) {
        if (core.getHash(oldBaseNode) !== core.getHash(newBaseNode)) {
            return false;
        }

        oldBaseNode = core.getBase(oldBaseNode);
        newBaseNode = core.getBase(newBaseNode);

        const oldGuid = oldBaseNode && core.getGuid(oldBaseNode);
        const newGuid = newBaseNode && core.getGuid(newBaseNode);

        if (oldGuid !== newGuid) {
            return false;
        }
    }

    return true;
}

/**
 * @param {GmeClasses.Core} core 
 * @param {string} resourceNodePath
 * @param {GmeClasses.Core.Node} oldNode
 * @param {GmeClasses.Core.Node} newNode
 * 
 * @returns {Promise<boolean>}
 */
async function propertiesAndRelationshipsSame(core, resourceNodePath, oldNode, newNode) {
    return attributesSame(core, oldNode, newNode)
        && await pointersSame(core, oldNode, newNode)
        && await connectionsSame(core, resourceNodePath, oldNode, newNode)
        && await setsSame(core, oldNode, newNode);
}

/**
 * @param {GmeClasses.Core} core 
 * @param {GmeClasses.Core.Node} oldNode
 * @param {GmeClasses.Core.Node} newNode
 * 
 * @returns {boolean}
 */
function attributesSame(core, oldNode, newNode) {
    const oldAttribtueNames = core.getAttributeNames(oldNode);
    const newAttribtueNames = core.getAttributeNames(oldNode);

    if (oldAttribtueNames.length !== newAttribtueNames.length) {
        return false;
    }

    const newSet = new Set(newAttribtueNames);

    for (const attrName of oldAttribtueNames) {
        if (!newSet.has(attrName)) {
            return false;
        }

        if (core.getAttribute(oldNode, attrName) !== core.getAttribute(newNode, attrName)) {
            return false;
        }
    }

    return true;
}

/**
 * @param {GmeClasses.Core} core 
 * @param {GmeClasses.Core.Node} oldNode
 * @param {GmeClasses.Core.Node} newNode
 * 
 * @returns {Promise<boolean>}
 */
async function pointersSame(core, oldNode, newNode) {
    const oldPointerNames = core.getPointerNames(oldNode);
    const newPointerNames = core.getPointerNames(oldNode);

    if (oldPointerNames.length !== newPointerNames.length) {
        return false;
    }

    const newSet = new Set(newPointerNames);

    for (const ptrName of oldPointerNames) {
        if (!newSet.has(ptrName)) {
            return false;
        }

        const oldTarget = await core.loadPointer(oldNode, ptrName);
        const newTarget = await core.loadPointer(newNode, ptrName);
        const oldTargetGuid = oldTarget && core.getGuid(oldTarget);
        const newTargetGuid = newTarget && core.getGuid(newTarget);

        if (oldTargetGuid !== newTargetGuid) {
            return false;
        }
    }

    return true;
}

/**
 * Check all the out-going connections from within the resource-node. 
 * Any connection-node that is defined within the node will be handled by pointersSame.
 * @param {GmeClasses.Core} core 
 * @param {string} resourceNodePath
 * @param {GmeClasses.Core.Node} oldNode
 * @param {GmeClasses.Core.Node} newNode
 * 
 * @returns {Promise<boolean>}
 */
async function connectionsSame(core, resourceNodePath, oldNode, newNode) {

    const oldConnTargetTypes = core.getCollectionNames(oldNode).filter(n => n === 'src');
    const newConnTargetTypes = core.getCollectionNames(newNode).filter(n => n === 'src');

    if (oldConnTargetTypes.length !== newConnTargetTypes.length) {
        return false;
    }

    if (oldConnTargetTypes.length === 0) {
        return true; // Both are empty
    }

    const oldConnNodes = await core.loadCollection(oldNode, 'src');
    const newConnNodes = await core.loadCollection(newNode, 'src');

    if (oldConnNodes.length !== newConnNodes.length) {
        return false;
    }

    const guidToNewConnNodes = new Map(newConnNodes.map(node => [core.getGuid(node), node]));

    for (const oldConnNode of oldConnNodes) {
        const oldGuid = core.getGuid(oldConnNode);
        if (!guidToNewConnNodes.has(oldGuid)) {
            return false;
        }

        const newConnNode = guidToNewConnNodes.get(oldGuid);
        const oldNodeWithinResourceNode = core.getPath(oldConnNode).startsWith(resourceNodePath);
        const newNodeWithinResourceNode = core.getPath(newConnNode).startsWith(resourceNodePath);
        if (oldNodeWithinResourceNode || newNodeWithinResourceNode) {
            // Connections are within resource-node -> handled by pointersSame.
            // (A moved resource-node is handled in a different branch.)
            continue;
        }


        // At this point we've found the corresponding connection nodes and they are outside of the resource node.
        if (!attributesSame(core, oldConnNode, newConnNode)) {
            // Attributes of the connection node changed.
            return false;
        }

        const oldTargetNode = await core.loadPointer(oldConnNode, 'dst');
        const newTargetNode = await core.loadPointer(newConnNode, 'dst');

        const oldTargetGuid = oldTargetNode && core.getGuid(oldTargetNode);
        const newTargetGuid = newTargetNode && core.getGuid(newTargetNode);

        if (oldTargetGuid !== newTargetGuid) {
            return false;
        }
    }

    return true;
}

/**
 * @param {GmeClasses.Core} core 
 * @param {GmeClasses.Core.Node} oldNode
 * @param {GmeClasses.Core.Node} newNode
 * 
 * @returns {Promise<boolean>}
 */
async function setsSame(core, oldNode, newNode) {
    const oldSetNames = core.getSetNames(oldNode);
    const newSetNames = core.getSetNames(newNode);

    if (oldSetNames.length !== newSetNames.length) {
        return false;
    }

    const oldRoot = core.getRoot(oldNode);
    const newRoot = core.getRoot(newNode);

    const newSet = new Set(newSetNames);

    async function loadMemberGuids(root, memberPaths) {
        const guids = new Set();

        for (const path in memberPaths) {
            const memberNode = await loadByPath(root, path);
            if (memberNode) {
                guids.add(core.getGuid(memberNode));
            }
        }

        return guids;
    }

    for (const setName of oldSetNames) {
        if (!newSet.has(setName)) {
            return false;
        }

        const oldMemberPaths = core.getMemberPaths(oldNode, setName);
        const newMemberPaths = core.getMemberPaths(newNode, setName);

        if (oldMemberPaths.length !== newMemberPaths.length) {
            return false;
        }

        const oldMemberGuids = await loadMemberGuids(oldRoot, oldMemberPaths);
        const newMemberGuids = await loadMemberGuids(newRoot, newMemberPaths);

        if (oldMemberGuids.size !== newMemberGuids.size) {
            return false;
        }

        for (const guid of oldMemberGuids) {
            if (!newMemberGuids.has(guid)) {
                return false;
            }
        }
    }

    return true;
}

module.exports = getResourceChanges;