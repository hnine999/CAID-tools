import * as grpc from '@grpc/grpc-js';
import * as depi from './pbs/depi_pb';
import * as crypto from 'crypto';
import { DepiClient } from './pbs/depi_grpc_pb';
import { addAsyncMethods } from './pbs/addAsyncMethods';
import {
    ResourcePattern,
    Resource,
    ResourceRef,
    ResourceGroup,
    ResourceLinkRef,
    ResourceLink,
    LinkPattern,
    ResourceChange,
    ResourceGroupRef,
} from './@types/depi';

export interface DepiSession {
    client: DepiClient;
    sessionId: string;
    branchName: string;
    token: string;
    user: string;
    watchers: {
        [key: string]: grpc.ClientReadableStream<any>;
    }
}

async function getDepiClient(url: string, cert: string = '', opts: object = {}) {
    let credentials: grpc.ChannelCredentials;
    if (cert) {
        credentials = grpc.credentials.createSsl(Buffer.from(cert, 'utf8'));
    } else {
        credentials = grpc.credentials.createInsecure();
    }

    // {'grpc.ssl_target_name_override': 'depi_server.isis.vanderbilt.edu'}
    const client = new DepiClient(url, credentials, opts);
    // generated client doesn't support promises/async await
    addAsyncMethods(client);

    return client;
}

export async function logInDepiClient(
    url: string,
    userName: string,
    password: string,
    cert: string = '',
    opts: object = {},
): Promise<DepiSession> {
    const client = await getDepiClient(url, cert, opts);

    const req = new depi.LoginRequest();
    req.setUser(userName);
    req.setPassword(password);

    let res = await client.loginAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not loginAsync ' + res.getMsg());
    }

    return {
        client,
        sessionId: res.getSessionid(),
        user: res.getUser(),
        token: res.getLogintoken(),
        branchName: 'main',
        watchers: {},
    };
}

export async function logInDepiClientWithToken(
    url: string,
    token: string,
    cert: string = '',
    opts: object = {},
): Promise<DepiSession> {
    const client = await getDepiClient(url, cert, opts);

    const req = new depi.LoginWithTokenRequest();
    req.setLogintoken(token);

    let res = await client.loginWithTokenAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not loginWithTokenAsync ' + res.getMsg());
    }

    return {
        client,
        sessionId: res.getSessionid(),
        user: res.getUser(),
        token: res.getLogintoken(),
        branchName: 'main',
        watchers: {},
    };
}

export async function ping(depiSession: DepiSession) {
    const req = new depi.PingRequest();
    req.setSessionid(depiSession.sessionId);

    const res = await depiSession.client.pingAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not pingAsync ' + res.getMsg());
    }

    return { token: res.getLogintoken() };
}

export async function logOut(depiSession: DepiSession) {
    const req = new depi.LogoutRequest();
    req.setSessionid(depiSession.sessionId);

    const res = await depiSession.client.logoutAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not logoutAsync ' + res.getMsg());
    }

    // depiSession.sessionId = null;
    // depiSession.client = null;

    for (const watcherId of Object.keys(depiSession.watchers)) {
        const stream = depiSession.watchers[watcherId];
        stream.cancel();
        delete depiSession.watchers[watcherId];
    }
}

/**
 * Set the branch on the server for the current session. If the branch does not exist, will return null.
 * @param depiSession
 * @param branchName
 * @returns {Promise<string|null>}
 */
export async function setBranch(depiSession: DepiSession, branchName: string): Promise<string | null> {
    const req = new depi.SetBranchRequest();
    req.setSessionid(depiSession.sessionId);
    req.setBranch(branchName);

    const res = await depiSession.client.setBranchAsync(req);

    if (!res.getOk()) {
        if (res.getMsg().includes('Unknown branch')) {
            return null;
        }

        throw new Error('Could not setBranchAsync ' + res.getMsg());
    }

    return branchName;
}

export async function createBranch(depiSession: DepiSession, branchName: string, fromBranch: string) {
    const req = new depi.CreateBranchRequest();
    req.setSessionid(depiSession.sessionId);
    req.setBranchname(branchName);
    req.setFrombranch(fromBranch);

    const res = await depiSession.client.createBranchAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not createBranchAsync ' + res.getMsg());
    }
}

export async function createTag(depiSession: DepiSession, tagName: string, fromBranch: string) {
    const req = new depi.CreateTagRequest();
    req.setSessionid(depiSession.sessionId);
    req.setTagname(tagName);
    req.setFrombranch(fromBranch);

    const res = await depiSession.client.createTagAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not createTagAsync ' + res.getMsg());
    }
}

export async function getBranchesAndTags(depiSession: DepiSession): Promise<{ branches: string[], tags: string[] }> {
    const req = new depi.GetBranchListRequest();
    req.setSessionid(depiSession.sessionId);

    const res = await depiSession.client.getBranchListAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not getBranchListAsync ' + res.getMsg());
    }

    return { branches: res.getBranchesList(), tags: res.getTagsList() };
}

export async function getResourceGroups(depiSession: DepiSession): Promise<ResourceGroup[]> {
    const req = new depi.GetResourceGroupsRequest();

    req.setSessionid(depiSession.sessionId);
    let res = await depiSession.client.getResourceGroupsAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not getResourceGroupsAsync ' + res.getMsg());
    }

    return res.getResourcegroupsList().map((rg) => {
        return {
            url: rg.getUrl(),
            toolId: rg.getToolid(),
            name: rg.getName(),
            pathDivider: '/', // FIXME: This should come fromt he tool-config on depi-server.
            version: rg.getVersion(),
            isActiveInEditor: false,
        };
    });
}

export async function getResources(depiSession: DepiSession, resourcePatterns: ResourcePattern[]): Promise<Resource[]> {
    const req = new depi.GetResourcesRequest();

    req.setSessionid(depiSession.sessionId);
    req.setPatternsList(resourcePatterns.map((rp) => getDepiResourceRefPattern(rp)));
    req.setIncludedeleted(false);

    const res = await depiSession.client.getResourcesAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not getResourcesAsync ' + res.getMsg());
    }

    return res.getResourcesList().map(getResourceObject);
}

export async function getResourcesStreamed(
    depiSession: DepiSession,
    resourcePatterns: ResourcePattern[])
    : Promise<Resource[]> {
    return new Promise((resolve, reject) => {
        const req = new depi.GetResourcesRequest();

        req.setSessionid(depiSession.sessionId);
        req.setPatternsList(resourcePatterns.map((rp) => getDepiResourceRefPattern(rp)));

        const call = depiSession.client.getResourcesAsStream(req);

        const resources: Resource[] = [];

        call.on('data', function (res: depi.GetResourcesAsStreamResponse) {
            if (!res.getOk()) {
                reject(new Error('Could not getResourcesAsStream ' + res.getMsg()));
                return;
            }

            resources.push(getResourceObject(res.getResource() as depi.Resource));
        });

        call.on('end', function () {
            resolve(resources);
        });

        call.on('error', function (error) {
            reject(error);
        });

        call.on('status', function (status) {
            // console.log('getResourcesAsStream::status::', status);
        });
    });
}

export async function getLinks(depiSession: DepiSession, linkPatterns: LinkPattern[]): Promise<ResourceLink[]> {
    const req = new depi.GetLinksRequest();

    req.setSessionid(depiSession.sessionId);
    req.setPatternsList(
        linkPatterns.map((linkPattern) => {
            const depiLinkPattern = new depi.ResourceLinkPattern();
            depiLinkPattern.setTores(getDepiResourceRefPattern(linkPattern.sourcePattern));
            depiLinkPattern.setFromres(getDepiResourceRefPattern(linkPattern.targetPattern));

            return depiLinkPattern;
        })
    );

    const res = await depiSession.client.getLinksAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not getLinksAsync ' + res.getMsg());
    }

    return res.getResourcelinksList().map(getLinkObject);
}

export async function getLinksStreamed(depiSession: DepiSession, linkPatterns: LinkPattern[]): Promise<ResourceLink[]> {
    return new Promise((resolve, reject) => {
        const req = new depi.GetLinksRequest();

        req.setSessionid(depiSession.sessionId);
        req.setPatternsList(
            linkPatterns.map((linkPattern) => {
                const depiLinkPattern = new depi.ResourceLinkPattern();
                depiLinkPattern.setTores(getDepiResourceRefPattern(linkPattern.sourcePattern));
                depiLinkPattern.setFromres(getDepiResourceRefPattern(linkPattern.targetPattern));

                return depiLinkPattern;
            })
        );

        const call = depiSession.client.getLinksAsStream(req);

        const resourceLinks: ResourceLink[] = [];

        call.on('data', function (res: depi.GetLinksAsStreamResponse) {
            if (!res.getOk()) {
                reject(new Error('Could not getLinksAsStream ' + res.getMsg()));
                return;
            }

            resourceLinks.push(getLinkObject(res.getResourcelink() as depi.ResourceLink));
        });

        call.on('end', function () {
            resolve(resourceLinks);
        });

        call.on('error', function (error) {
            reject(error);
        });

        call.on('status', function (status) {
            // console.log('getLinksAsStream::status::', status);
        });
    });
}

export async function getAllLinksStreamed(depiSession: DepiSession, includeDeleted: boolean = false): Promise<ResourceLink[]> {
    return new Promise((resolve, reject) => {
        const req = new depi.GetAllLinksAsStreamRequest();
        req.setSessionid(depiSession.sessionId);
        req.setIncludedeleted(includeDeleted);

        const call = depiSession.client.getAllLinksAsStream(req);
        const resourceLinks: ResourceLink[] = [];

        call.on('data', function (res: depi.GetLinksAsStreamResponse) {
            if (!res.getOk()) {
                reject(new Error('Could not getAllLinksAsStream ' + res.getMsg()));
                return;
            }

            resourceLinks.push(getLinkObject(res.getResourcelink() as depi.ResourceLink));
        });

        call.on('end', function () {
            resolve(resourceLinks);
        });

        call.on('error', function (error) {
            reject(error);
        });

        call.on('status', function (status) {
            // console.log('getAllLinksAsStream::status::', status);
        });
    });
}

export async function getDirtyLinks(depiSession: DepiSession, resourceGroup: ResourceGroup): Promise<ResourceLink[]> {
    const req = new depi.GetDirtyLinksRequest();

    req.setSessionid(depiSession.sessionId);
    req.setToolid(resourceGroup.toolId);
    req.setName(resourceGroup.name);
    req.setUrl(resourceGroup.url);

    const res = await depiSession.client.getDirtyLinksAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not getDirtyLinksAsync ' + res.getMsg());
    }

    return res.getLinksList().map(getLinkObject);
}

export async function getDepiModel(
    depiSession: DepiSession,
    activeResourceGroups: ResourceGroupRef[]
): Promise<{
    resourceGroups: ResourceGroup[];
    resources: Resource[];
    links: ResourceLink[];
}> {
    const resourceGroups = await getResourceGroups(depiSession);
    let resources: Resource[] = [];
    let links: ResourceLink[] = [];

    if (activeResourceGroups.length === 0) {
        return { resourceGroups, resources, links };
    }

    const patterns = resourceGroups
        .filter((resourceGroup) => {
            for (const rg of activeResourceGroups) {
                if (resourceGroup.toolId == rg.toolId && resourceGroup.url === rg.url) {
                    resourceGroup.isActiveInEditor = true;
                    return true;
                }
            }

            return false;
        })
        .map((resourceGroup) => ({
            toolId: resourceGroup.toolId,
            resourceGroupName: resourceGroup.name,
            resourceGroupUrl: resourceGroup.url,
            // For resources
            urlPattern: '.*',
        }));

    const linkPatterns: LinkPattern[] = [];
    for (const pattern of patterns) {
        resources = resources.concat(await getResourcesStreamed(depiSession, [pattern]));

        for (const targetPattern of patterns) {
            linkPatterns.push({ sourcePattern: pattern, targetPattern });
        }
    }

    if (patterns.length === resourceGroups.length) {
        links = await getAllLinksStreamed(depiSession);
    } else {
        links = await getLinksStreamed(depiSession, linkPatterns);
    }

    return { resourceGroups, resources, links };
}

export async function getBlackboardModel(
    depiSession: DepiSession
): Promise<{ resources: Resource[]; links: ResourceLink[] }> {
    const req = new depi.GetBlackboardResourcesRequest();
    req.setSessionid(depiSession.sessionId);
    const res = await depiSession.client.getBlackboardResourcesAsync(req);
    if (!res.getOk()) {
        throw new Error('Could not getBlackboardResourcesAsync ' + res.getMsg());
    }

    const resources = res.getResourcesList().map(getResourceObject);
    const links = res.getLinksList().map(getLinkObject);

    return { resources, links };
}

/**
 * Returns all dependencies, including implicit ones, of the provided resource-ref.
 * If the resource is not in depi - the call succeeds but resource in the result will be null.
 * @param depiSession 
 * @param resourceRef 
 * @param reverse - If true will return dependants of the resource instead of dependencies.
 * @returns 
 */
export async function getDependencyGraph(
    depiSession: DepiSession,
    resourceRef: ResourceRef,
    reverse: boolean = false,
): Promise<{ resource: Resource | null, links: ResourceLink[] }> {
    const req = new depi.GetDependencyGraphRequest();
    req.setSessionid(depiSession.sessionId);
    req.setResource(getDepiResourceRef(resourceRef));
    req.setDependenciestype(depi.DependenciesType.DEPENDENCIES);
    if (reverse) {
        req.setDependenciestype(1);
    }

    const res = await depiSession.client.getDependencyGraphAsync(req);
    if (!res.getOk()) {
        if (res.getMsg().includes("Parent resource not found")) {
            return { resource: null, links: [] };
        }
        throw new Error('Could not getDependencyGraphAsync ' + res.getMsg());
    }

    return {
        resource: getResourceObject(res.getResource() as depi.Resource),
        links: res.getLinksList().map(getLinkObject)
    };
}

/**
 * Returns all direct dependencies of the resource.
 * If the resource is not in depi - the call succeeds but resource in the result will be null.
 * @param depiSession 
 * @param resourceRef 
 * @param reverse - If true will return dependants of the resource instead of dependencies.
 * @returns 
 */
export async function getDependencies(
    depiSession: DepiSession,
    resourceRef: ResourceRef,
    reverse: boolean = false,
): Promise<{ resource: Resource | null, links: ResourceLink[] }> {
    const req = new depi.GetDependencyGraphRequest();
    req.setSessionid(depiSession.sessionId);
    req.setResource(getDepiResourceRef(resourceRef));
    req.setDependenciestype(depi.DependenciesType.DEPENDENCIES);
    req.setMaxdepth(1);
    if (reverse) {
        req.setDependenciestype(1);
    }

    const res = await depiSession.client.getDependencyGraphAsync(req);
    if (!res.getOk()) {
        if (res.getMsg().includes("Parent resource not found")) {
            return { resource: null, links: [] };
        }
        throw new Error('Could not getDependencyGraphAsync (maxDepth:1)' + res.getMsg());
    }

    return {
        resource: getResourceObject(res.getResource() as depi.Resource),
        links: res.getLinksList().map(getLinkObject)
    };
}

// Setters API
export async function addResourcesToBlackboard(depiSession: DepiSession, resources: Resource[]) {
    const resourceReq = new depi.AddResourcesToBlackboardRequest();
    resourceReq.setSessionid(depiSession.sessionId);
    for (let resource of resources) {
        resourceReq.addResources(getDepiResource(resource));
    }

    const resourceRes = await depiSession.client.addResourcesToBlackboardAsync(resourceReq);
    if (!resourceRes.getOk()) {
        throw new Error('Could not addResourcesToBlackboardAsync: ' + resourceRes.getMsg());
    }
}

export async function addLinkToBlackboard(depiSession: DepiSession, source: Resource, target: Resource) {
    const resourceReq = new depi.AddResourcesToBlackboardRequest();
    resourceReq.setSessionid(depiSession.sessionId);
    resourceReq.addResources(getDepiResource(source));
    resourceReq.addResources(getDepiResource(target));

    const resourceRes = await depiSession.client.addResourcesToBlackboardAsync(resourceReq);
    if (!resourceRes.getOk()) {
        throw new Error('Could not addResourcesToBlackboardAsync ' + resourceRes.getMsg());
    }

    const linkReq = new depi.LinkBlackboardResourcesRequest();
    linkReq.setSessionid(depiSession.sessionId);

    const depiLink = new depi.ResourceLink();
    depiLink.setTores(getDepiResource(source));
    depiLink.setFromres(getDepiResource(target));
    depiLink.setDeleted(false);

    linkReq.addLinks(depiLink);

    const linkRes = await depiSession.client.linkBlackboardResourcesAsync(linkReq);
    if (!linkRes.getOk()) {
        throw new Error('Could not linkBlackboardResourcesAsync ' + linkRes.getMsg());
    }
}

export async function saveBlackboard(depiSession: DepiSession) {
    const req = new depi.SaveBlackboardRequest();
    req.setSessionid(depiSession.sessionId);
    const res = await depiSession.client.saveBlackboardAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not saveBlackboardAsync ' + res.getMsg());
    }
}

export async function clearBlackboard(depiSession: DepiSession) {
    const req = new depi.ClearBlackboardRequest();
    req.setSessionid(depiSession.sessionId);
    const res = await depiSession.client.clearBlackboardAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not clearBlackboardAsync ' + res.getMsg());
    }
}

export async function removeEntriesFromBlackboard(
    depiSession: DepiSession,
    entries: { links: ResourceLink[]; resources: Resource[] }
) {
    const links: depi.ResourceLinkRef[] = entries.links.map((entry) => {
        const link = new depi.ResourceLinkRef();
        link.setFromres(getDepiResourceRef(entry.target));
        link.setTores(getDepiResourceRef(entry.source));
        return link;
    });

    const resources: depi.ResourceRef[] = entries.resources.map((entry) => getDepiResourceRef(entry));

    if (links.length > 0) {
        const unlinkReq = new depi.UnlinkBlackboardResourcesRequest();
        unlinkReq.setSessionid(depiSession.sessionId);
        unlinkReq.setLinksList(links);
        const unlinkRes = await depiSession.client.unlinkBlackboardResourcesAsync(unlinkReq);

        if (!unlinkRes.getOk()) {
            throw new Error('Could not RemoveResourcesFromBlackboardRequest ' + unlinkRes.getMsg());
        }
    }

    if (resources.length > 0) {
        const removeResourcesReq = new depi.RemoveResourcesFromBlackboardRequest();
        removeResourcesReq.setSessionid(depiSession.sessionId);
        removeResourcesReq.setResourcerefsList(resources);
        const removeResourcesRes = await depiSession.client.removeResourcesFromBlackboardAsync(removeResourcesReq);

        if (!removeResourcesRes.getOk()) {
            throw new Error('Could not RemoveResourcesFromBlackboardRequest ' + removeResourcesRes.getMsg());
        }
    }
}

export async function deleteEntriesFromDepi(
    depiSession: DepiSession,
    entries: { links: ResourceLink[]; resources: Resource[] }
) {
    const req = new depi.UpdateDepiRequest();
    req.setSessionid(depiSession.sessionId);

    const updates: depi.Update[] = entries.resources.map((entry) => {
        const update = new depi.Update();
        update.setUpdatetype(depi.UpdateType.REMOVERESOURCE);
        update.setResource(getDepiResource(entry));

        return update;
    });

    entries.links.forEach((entry) => {
        const update = new depi.Update();

        update.setUpdatetype(depi.UpdateType.REMOVELINK);
        const link = new depi.ResourceLink();
        link.setFromres(getDepiResource(entry.target));
        link.setTores(getDepiResource(entry.source));
        update.setLink(link);
        updates.push(update);
    });

    req.setUpdatesList(updates);

    const res = await depiSession.client.updateDepiAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not deleteEntriesFromDepi via updateDepiAsync ' + res.getMsg());
    }
}

export async function markLinksClean(
    depiSession: DepiSession,
    links: ResourceLinkRef[],
    propagate: boolean | undefined
) {
    const req = new depi.MarkLinksCleanRequest();
    req.setSessionid(depiSession.sessionId);

    const depiLinks: depi.ResourceLinkRef[] = links.map((link) => {
        const depiLink = new depi.ResourceLinkRef();
        depiLink.setFromres(getDepiResourceRef(link.target));
        depiLink.setTores(getDepiResourceRef(link.source));
        return depiLink;
    });

    req.setLinksList(depiLinks);
    req.setPropagatecleanliness(Boolean(propagate));

    const res = await depiSession.client.markLinksCleanAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not markLinksCleanAsync ' + res.getMsg());
    }
}

export async function markInferredDirtinessClean(
    depiSession: DepiSession,
    link: ResourceLinkRef,
    dirtinessSource: ResourceRef,
    propagate: boolean | undefined
) {
    const req = new depi.MarkInferredDirtinessCleanRequest();
    req.setSessionid(depiSession.sessionId);

    req.setLink(getDepiResourceLinkRef(link));
    req.setDirtinesssource(getDepiResourceRef(dirtinessSource));
    req.setPropagatecleanliness(Boolean(propagate));

    const res = await depiSession.client.markInferredDirtinessCleanAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not markInferredDirtinessCleanAsync' + res.getMsg());
    }
}

export async function updateResourceGroup(
    depiSession: DepiSession,
    toolId: string,
    resourceGroupName: string,
    resourceGroupUrl: string,
    newVersion: string,
    resourceChanges: ResourceChange[],
) {
    const req = new depi.UpdateResourceGroupRequest();
    req.setSessionid(depiSession.sessionId);

    const resourceGroupChange = new depi.ResourceGroupChange();
    resourceGroupChange.setToolid(toolId);
    resourceGroupChange.setName(resourceGroupName);
    resourceGroupChange.setUrl(resourceGroupUrl);
    resourceGroupChange.setVersion(newVersion);
    resourceGroupChange.setResourcesList(resourceChanges.map(rc => getDepiResourceChange(rc)));

    req.setResourcegroup(resourceGroupChange);
    const res = await depiSession.client.updateResourceGroupAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not updateResourceGroupAsync ' + res.getMsg());
    }
}

export async function editResourceGroupProperties(
    depiSession: DepiSession,
    resourceGroupRef: ResourceGroupRef,
    newName: string,
    newToolId: string,
    newUrl: string,
    newVersion: string
) {
    const req = new depi.EditResourceGroupRequest();
    req.setSessionid(depiSession.sessionId);

    const resourceGroupEdit = new depi.ResourceGroupEdit();

    resourceGroupEdit.setToolid(resourceGroupRef.toolId);
    resourceGroupEdit.setUrl(resourceGroupRef.url);

    resourceGroupEdit.setNewName(newName);
    resourceGroupEdit.setNewToolid(newToolId);
    resourceGroupEdit.setNewUrl(newUrl);
    resourceGroupEdit.setNewVersion(newVersion);

    req.setResourcegroup(resourceGroupEdit);

    const res = await depiSession.client.editResourceGroupAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not editResourceGroupAsync ' + res.getMsg());
    }
}

export async function removeResourceGroup(
    depiSession: DepiSession,
    resourceGroupRef: ResourceGroupRef,
) {
    const req = new depi.RemoveResourceGroupRequest();
    req.setSessionid(depiSession.sessionId);

    const rgRef = new depi.ResourceGroupRef();

    rgRef.setToolid(resourceGroupRef.toolId);
    rgRef.setUrl(resourceGroupRef.url);

    req.setResourcegroup(rgRef);

    const res = await depiSession.client.removeResourceGroupAsync(req);

    if (!res.getOk()) {
        throw new Error('Could not removeResourceGroupAsync ' + res.getMsg());
    }
}

export async function markAllClean(depiSession: DepiSession, links: ResourceLink[], log: Function) {
    log('Marking all clean, nbr of links: ', links.length);
    for (const link of links) {
        if (link.dirty) {
            log('  link is dirty - marking clean');
            await markLinksClean(depiSession, [link], false);
        }

        let cnt = 1;
        for (const { resource } of link.inferredDirtiness) {
            log('  link as inferred dirty resource ', cnt);
            cnt += 1;
            await markInferredDirtinessClean(depiSession, link, resource, false);
        }
    }
}

export async function watchBlackboard(
    depiSession: DepiSession,
    onData: (data: any) => void,
    onError: (data: any) => void,
): Promise<string> {
    const watchRequest = new depi.WatchBlackboardRequest();
    watchRequest.setSessionid(depiSession.sessionId);
    const stream = depiSession.client.watchBlackboard(watchRequest);

    stream.on('data', onData);
    stream.on('error', (err: any) => {
        if (err.message && err.message.includes('Cancelled on client')) {
            // Expected error event at close
            return;
        }

        onError(err);
    });

    // TODO: See if these are ever called..
    stream.on('end', () => {
        throw new Error('end event');
    });
    stream.on('status', (status) => {
        throw new Error('status event' + status);
    });

    const watcherId = crypto.randomUUID().toString();
    depiSession.watchers[watcherId] = stream;

    return watcherId;
}

export async function unwatchBlackboard(depiSession: DepiSession, watcherId: string) {
    const unwatchRequest = new depi.UnwatchBlackboardRequest();
    unwatchRequest.setSessionid(depiSession.sessionId);

    const res = await depiSession.client.unwatchBlackboardAsync(unwatchRequest);

    if (!res.getOk()) {
        throw new Error('Could not unwatchBlackboardAsync ' + res.getMsg());
    }

    const stream = depiSession.watchers[watcherId];
    stream.cancel();
    delete depiSession.watchers[watcherId];
}

export async function watchDepi(
    depiSession: DepiSession,
    onData: (data: any) => void,
    onError: (data: any) => void,
): Promise<string> {
    const watchRequest = new depi.WatchDepiRequest();
    watchRequest.setSessionid(depiSession.sessionId);
    const stream = depiSession.client.watchDepi(watchRequest);

    stream.on('data', onData);
    stream.on('error', (err: any) => {
        if (err.message && err.message.includes('Cancelled on client')) {
            // Expected error event at close
            return;
        }

        onError(err);
    });

    // TODO: See if these are ever called..
    stream.on('end', () => {
        throw new Error('end event');
    });
    stream.on('status', (status) => {
        throw new Error('status event' + status);
    });

    const watcherId = crypto.randomUUID().toString();
    depiSession.watchers[watcherId] = stream;

    return watcherId;
}

export async function unwatchDepi(depiSession: DepiSession, watcherId: string) {
    const unwatchRequest = new depi.UnwatchDepiRequest();
    unwatchRequest.setSessionid(depiSession.sessionId);

    const res = await depiSession.client.unwatchDepiAsync(unwatchRequest);

    if (!res.getOk()) {
        throw new Error('Could not unwatchDepiAsync ' + res.getMsg());
    }

    const stream = depiSession.watchers[watcherId];
    stream.cancel();
    delete depiSession.watchers[watcherId];
}

export function isSameResource(r1?: ResourceRef, r2?: ResourceRef) {
    if (!r1 || !r2) {
        return false;
    }

    return r1.toolId === r2.toolId && r1.resourceGroupUrl === r2.resourceGroupUrl && r1.url === r2.url;
}

export function isSameResourceGroup(r1?: ResourceGroupRef, r2?: ResourceGroupRef) {
    if (!r1 || !r2) {
        return false;
    }

    return r1.toolId === r2.toolId && r1.url === r2.url;
}

export function isSameResourceLink(link1?: ResourceLinkRef, link2?: ResourceLinkRef) {
    if (!link1 || !link2) {
        return false;
    }

    return isSameResource(link1.source, link2.source) && isSameResource(link1.target, link2.target);
}

const methods = {
    logInDepiClient,
    logInDepiClientWithToken,
    logOut,
    ping,
    setBranch,
    createBranch,
    createTag,
    getBranchesAndTags,
    getResourceGroups,
    getResources,
    getResourcesStreamed,
    getLinks,
    getLinksStreamed,
    getAllLinksStreamed,
    getDirtyLinks,
    getDepiModel,
    getBlackboardModel,
    getDependencyGraph,
    getDependencies,
    addResourcesToBlackboard,
    addLinkToBlackboard,
    saveBlackboard,
    clearBlackboard,
    removeEntriesFromBlackboard,
    deleteEntriesFromDepi,
    markLinksClean,
    markInferredDirtinessClean,
    markAllClean,
    updateResourceGroup,
    editResourceGroupProperties,
    removeResourceGroup,
    // Compare functions
    isSameResource,
    isSameResourceGroup,
    isSameResourceLink,
    // Watchers
    watchBlackboard,
    unwatchBlackboard,
    watchDepi,
    unwatchDepi,
};

export default methods;

// Conversion functions
function getDepiResource(resource: Resource): depi.Resource {
    const res = new depi.Resource();
    res.setToolid(resource.toolId);
    res.setResourcegroupname(resource.resourceGroupName);
    res.setResourcegroupurl(resource.resourceGroupUrl);
    res.setResourcegroupversion(resource.resourceGroupVersion);
    res.setName(resource.name);
    res.setUrl(resource.url);
    res.setId(resource.id);
    res.setDeleted(resource.deleted);
    return res;
}

function getDepiResourceRef(resource: ResourceRef): depi.ResourceRef {
    const res = new depi.ResourceRef();
    res.setToolid(resource.toolId);
    res.setResourcegroupurl(resource.resourceGroupUrl);
    res.setUrl(resource.url);
    return res;
}

function getDepiResourceLinkRef(link: ResourceLinkRef): depi.ResourceLinkRef {
    const res = new depi.ResourceLinkRef();
    res.setTores(getDepiResourceRef(link.source));
    res.setFromres(getDepiResourceRef(link.target));
    return res;
}

function getResourceObject(depiResource: depi.Resource): Resource {
    return {
        toolId: depiResource.getToolid(),
        resourceGroupName: depiResource.getResourcegroupname(),
        resourceGroupUrl: depiResource.getResourcegroupurl(),
        resourceGroupVersion: depiResource.getResourcegroupversion(),
        name: depiResource.getName(),
        url: depiResource.getUrl(),
        id: depiResource.getId(),
        deleted: depiResource.getDeleted(),
    };
}

function getLinkObject(depiLink: depi.ResourceLink): ResourceLink {
    return {
        source: getResourceObject(depiLink.getTores() as depi.Resource),
        target: getResourceObject(depiLink.getFromres() as depi.Resource),
        deleted: depiLink.getDeleted(),
        dirty: depiLink.getDirty(),
        lastCleanVersion: depiLink.getLastcleanversion(),
        inferredDirtiness: depiLink.getInferreddirtinessList().map((dirtiness) => ({
            resource: getResourceObject(dirtiness.getResource() as depi.Resource),
            lastCleanVersion: dirtiness.getLastcleanversion(),
        })),
    };
}

function getDepiResourceRefPattern(resourcePattern: ResourcePattern): depi.ResourceRefPattern {
    const res = new depi.ResourceRefPattern();

    res.setToolid(resourcePattern.toolId);
    res.setResourcegroupurl(resourcePattern.resourceGroupUrl);
    res.setUrlpattern(resourcePattern.urlPattern);

    return res;
}

function getDepiResourceChange(resourceChange: ResourceChange): depi.ResourceChange {
    const res = new depi.ResourceChange();

    res.setName(resourceChange.name);
    res.setNewName(resourceChange.newName);
    res.setUrl(resourceChange.url);
    res.setNewUrl(resourceChange.newUrl);
    res.setId(resourceChange.id);
    res.setNewId(resourceChange.newId);
    res.setChangetype(resourceChange.changeType);

    return res;
}
