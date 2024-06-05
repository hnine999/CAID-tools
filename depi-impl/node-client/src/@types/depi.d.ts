export interface ResourceGroupRef {
    url: string;
    toolId: string;
}

export interface ResourceGroup extends ResourceGroupRef{
    name: string;
    version: string;
    pathDivider: string;
    isActiveInEditor: boolean;
}

export interface ResourceRef {
    toolId: string;
    resourceGroupUrl: string;
    url: string;
}

export interface Resource extends ResourceRef {
    resourceGroupName: string;
    resourceGroupVersion: string;
    name: string;
    id: string;
    deleted: boolean;
}

export interface ResourcePattern {
    toolId: string;
    resourceGroupUrl: string;
    urlPattern: string;
}

export interface ResourceLinkRef {
    source: ResourceRef;
    target: ResourceRef;
}

export interface ResourceLink {
    source: Resource;
    target: Resource;
    deleted: boolean;
    dirty: boolean;
    lastCleanVersion: string;
    inferredDirtiness: { resource: Resource; lastCleanVersion: string }[];
}

export interface LinkPattern {
    sourcePattern: ResourcePattern;
    targetPattern: ResourcePattern;
}

export enum ChangeType {
    Added = 0,
    Modified = 1,
    Renamed = 2,
    Removed = 3,
}

export interface ResourceChange {
    name: string;
    url: string;
    id: string;
    changeType: ChangeType;
    newName: string;
    newUrl: string;
    newId: string;
}
