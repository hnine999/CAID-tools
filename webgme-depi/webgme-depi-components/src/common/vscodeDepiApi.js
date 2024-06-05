/* eslint-disable import/no-amd */
/* globals define */

define(['./CONSTANTS'], (CONSTANTS) => {
    const { EVENTS } = CONSTANTS;
    let client;
    const pendingResult = {};
    const eventHandlers = {};

    function sendMessage(type, data) {
        const commandId = window.crypto.randomUUID();
        const message = { commandId, type, data };
        console.log(`Inside WebGME frame: sending message ${JSON.stringify(message)}`);
        window.parent.postMessage(message, '*');

        const promise = new Promise((resolve, reject) => {
            pendingResult[commandId] = { resolve, reject };
        });

        return promise;
    }

    return function initializeApi(client_) {
        if (!client) {
            client = client_;

            window.onmessage = (event) => {
                if (event.source === window) {
                    return;
                }

                const { data } = event;
                console.log('Inside WebGME frame: data received', JSON.stringify(data));
                const { commandId, result, error } = data;

                if (!commandId) {
                    // Server events
                    const handlers = eventHandlers[data.type];
                    if (handlers && handlers.length > 0) {
                        handlers.forEach(fn => fn(data));
                    } else {
                        console.log('No event handler for', data.type);
                    }

                    return;
                }

                const deferred = pendingResult[commandId];
                delete pendingResult[commandId];

                if (error) {
                    deferred.reject(new Error(error));
                } else {
                    deferred.resolve(result);
                }
            };
        }

        return {
            available: false,
            getResourceGroupInfo() {
                return {
                    toolId: 'webgme',
                    resourceGroupName: `webgme:${client.getActiveProjectName()}`,
                    resourceGroupUrl: `${client.gmeConfig.plugin.webgmePublicUrl}?project=${client.getActiveProjectId()}`,
                    resourceGroupVersion: client.getActiveCommitHash(), // TODO: What if tags are used?
                }
            },
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
                const handlers = eventHandlers[CONSTANTS.EVENTS.DEPI_UPDATED] || [];
                handlers.push(fn);
                eventHandlers[CONSTANTS.EVENTS.DEPI_UPDATED] = handlers;
            },
            /**
             * 
             * @param {Function} fn 
             */
            removeOnDepiUpdatedHandler(fn) {
                eventHandlers[CONSTANTS.EVENTS.DEPI_UPDATED] = eventHandlers[CONSTANTS.EVENTS.DEPI_UPDATED]
                    .filter(fnOther => fn !== fnOther);
            },
            /**
             * @returns {Promise<string>}
             */
            async getBranchName() {
                const promise = new Promise(async (resolve, reject) => {
                    const tid = setTimeout(() => {
                        reject(new Error('No Depi'));
                    }, 2000);

                    const branchName = await sendMessage(EVENTS.GET_BRANCH_NAME);
                    clearTimeout(tid);
                    resolve(branchName);
                });

                return promise;
            },
            /**
             * @param {object[]} resourceRefs - the resources to get info about
             * @returns {Promise}
             */
            getResourceInfo(resourceRefs) {
                return sendMessage(EVENTS.GET_RESOURCE_INFO, resourceRefs);
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
                return sendMessage(EVENTS.REVEAL_RESOURCE, resource);
            },
            /**
             * @param {object} resourceRef - the resource to get all ((including implicit) dependencies of.
             * @returns {Promise}
             */
            getDependencyGraph(resourceRef) {
                return sendMessage(EVENTS.GET_DEPENDENCY_GRAPH, resourceRef);
            },
            /**
             * @param {object} resourceRef - the resource to get all (including implicit) dependants of.
             * @returns {Promise}
             */
            getDependantsGraph(resourceRef) {
                return sendMessage(EVENTS.GET_DEPENDANTS_GRAPH, resourceRef);
            },
            /**
             * @param {object} resourceRef - the resource to get direct dependencies of.
             * @returns {Promise}
             */
            getDependencies(resourceRef) {
                return sendMessage(EVENTS.GET_DEPENDENCIES, resourceRef);
            },
            /**
             * @param {object} resourceRef - the resource to get direct dependants of.
             * @returns {Promise}
             */
            getDependants(resourceRef) {
                return sendMessage(EVENTS.GET_DEPENDANTS, resourceRef);
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
