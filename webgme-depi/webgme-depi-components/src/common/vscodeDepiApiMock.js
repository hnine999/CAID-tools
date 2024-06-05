/* eslint-disable import/no-amd */
/* globals define */

define(['./CONSTANTS'], (CONSTANTS) => {
    let client;

    const proofRes = {
        toolId: 'git',
        resourceGroupName: 'Evidence.git',
        resourceGroupUrl: 'http://localhost:3001/patrik/Evidence.git',
        resourceGroupVersion: 'b859fcf89d045188d98d6268d1213532075aca6a',
        name: 'proof.zip',
        url: '/proof.zip',
        id: '/proof.zip',
        deleted: false,
    };

    const pythonFileRes = {
        toolId: 'git',
        resourceGroupName: 'python-sources.git',
        resourceGroupUrl: 'http://localhost:3001/patrik/python-sources.git',
        resourceGroupVersion: 'fa00b1afb1220c37298c0ea3c8d8767cffe7d8ba',
        name: 'pythonFile.py',
        url: '/pythonFile.py',
        id: '/pythonFile.py',
        deleted: false,
    };

    const cFileRes = {
        toolId: 'git',
        resourceGroupName: 'c-sources.git',
        resourceGroupUrl: 'http://localhost:3001/patrik/c-sources.git',
        resourceGroupVersion: '6d345396ac27cb7e1af5ff9d94d6e02600805363',
        name: 'cFile.c',
        url: '/folder/cFile.c',
        id: '/folder/cFile.c',
        deleted: false,
    };


    return function initializeApi(client_) {
        client = client_
        const getResourceGroupInfo = () => ({
            toolId: 'webgme',
            resourceGroupName: `webgme:${client.getActiveProjectName()}@${client.getActiveBranchName()}`,
            resourceGroupUrl: `${window.location.origin}/?project=${client.getActiveProjectId()}&branch=${client.getActiveBranchName()}`,
            resourceGroupVersion: client.getActiveCommitHash(), // TODO: What if tags are used?
        });

        const refToResource = (ref) => ({
            ...ref,
            id: crypto.randomUUID(),
            name: `${ref.url.replace(/\//g, '')}mock_name`,
            ...getResourceGroupInfo()
        });

        const getLink = ({source, target, dirty}) => ({
            source,
            target,
            deleted: false,
            dirty: Boolean(dirty),
            lastCleanVersion: '',
            inferredDirtiness: [],
        });

        return {
            available: false,
            getResourceGroupInfo,
            isSameResource(r1, r2) {
                if (!r1 || !r2) {
                    return false;
                }

                return r1.toolId === r2.toolId && r1.resourceGroupUrl === r2.resourceGroupUrl && r1.url == r2.url;
            },
            /**
             * 
             * @param {Function} fn 
             */
            addOnDepiUpdatedHandler(fn) {
                console.log('addOnDepiUpdatedHandler');
            },
            /**
             * 
             * @param {Function} fn 
             */
            removeOnDepiUpdatedHandler(fn) {
                console.log('removeOnDepiUpdatedHandler');
            },
            /**
             * @returns {Promise<string>}
             */
            getBranchName() {
                return new Promise((resolve, reject) => {
                    setTimeout(() => {
                        resolve('main');
                    });
                });
            },
            /**
             * @param {object[]} resourceRefs - the resources to get info about
             * @returns {Promise}
             */
            getResourceInfo(resourceRefs) {
                return new Promise((resolve, reject) => {
                    const result = resourceRefs.map(refToResource);
                    result.shift();
                    setTimeout(() => {
                        resolve(result);
                    });
                });
            },
            /**
             * @param {object} resourceRef - the resource to show dependencies of.
             * @returns {Promise}
             */
            showDependencyGraph(resourceRef) {
                return sendMessage(EVENTS.SHOW_DEPENDENCY_GRAPH, resourceRef);
            },
            /**
             * @param {object} resourceRef - the resource to show dependants of.
             * @returns {Promise}
             */
            showDependantsGraph(resourceRef) {
                return sendMessage(EVENTS.SHOW_DEPENDANTS_GRAPH, resourceRef);
            },
            /**
             * @returns {Promise}
             */
            showBlackboard() {
                return sendMessage(EVENTS.SHOW_BLACKBOARD);
            },
            /**
             * @param {object} resource - the resource to reveal
             * @returns {Promise}
             */
            revealResource(resource) {
                return new Promise((resolve, reject) => {
                    setTimeout(() => {
                        alert("REVEAL:" + JSON.stringify(resource, null, 2));
                        resolve();
                    });
                });
            },
            /**
             * @param {object} resourceRef - the resource to get dependencies of.
             * @returns {Promise}
             */
            getDependencyGraph(resourceRef) {
                return new Promise((resolve, reject) => {
                    setTimeout(() => {
                        resolve({
                            resource: refToResource(resourceRef),
                            links: [
                                { source: refToResource(resourceRef), target: pythonFileRes },
                                { source: pythonFileRes, target: cFileRes, dirty: true }
                            ].map(getLink),
                        });
                    });
                });
            },
            /**
             * @param {object} resourceRef - the resource to get dependants of.
             * @returns {Promise}
             */
            getDependantsGraph(resourceRef) {
                return new Promise((resolve, reject) => {
                    setTimeout(() => {
                        resolve({
                            resource: refToResource(resourceRef),
                            links: [
                                { source: proofRes, target: refToResource(resourceRef) },
                            ].map(getLink),
                        });
                    });
                });
            },
            /**
             * @param {object} resource - the resource to add
             * @returns {Promise}
             */
            addAsResource(resource) {
                return sendMessage(EVENTS.ADD_AS_RESOURCE, resource);
            },
            /**
             * Removes the resource completely from depi.
             * Clear the depi-id attribute as part of this.
             * @param {object} resource - the resource to remove
             * @returns {Promise}
             */
            removeAsResource(resource) {
                return sendMessage(EVENTS.REMOVE_AS_RESOURCE, resource);
            },
            /**
             * @param {object} resource - the resource to add a dependency to (dependency will be selected)
             * @returns {Promise}
             */
            addDependency(resource) {
                return sendMessage(EVENTS.ADD_DEPENDENCY, resource);
            },
            /**
             * Removes the link to dependencyResource from resource
             * @param {object} resource - the resource
             * @param {object} dependencyResource - the resource to unlink
             * @returns {Promise}
             */
            removeDependency(resource, dependencyResource) {
                return sendMessage(EVENTS.REMOVE_DEPENDENCY, { source: resource, target: dependencyResource });
            },
            /**
             * @param {object} resource - the resource to add a dependant to (dependant will be selected)
             * @returns {Promise}
             */
            addDependant(resource) {
                return sendMessage(EVENTS.ADD_DEPENDANT, resource);
            },
            /**
             * Removes the link from dependantResource to resource
             * @param {object} resource - the resource
             * @param {object} dependantResource - the resource to unlink
             * @returns {Promise}
             */
            removeDependant(resource, dependantResource) {
                return sendMessage(EVENTS.REMOVE_DEPENDANT, { source: dependantResource, target: resource });
            },
        };
    };
});
