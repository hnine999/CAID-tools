import PropTypes from 'prop-types';

export const ResourceRef = PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string,
    url: PropTypes.string,
    resourceGroupUrl: PropTypes.string,
});

export const Resource = PropTypes.shape({
    toolId: PropTypes.string,
    resourceGroupName: PropTypes.string,
    resourceGroupUrl: PropTypes.string,
    resourceGroupVersion: PropTypes.string,
    id: PropTypes.string,
    name: PropTypes.string,
    url: PropTypes.string,
    labels: PropTypes.arrayOf(PropTypes.string),
});

export const ResourceGroup = PropTypes.shape({
    name: PropTypes.string,
    toolId: PropTypes.string,
    url: PropTypes.string,
    pathDivider: PropTypes.string,
    version: PropTypes.string,
    isActiveInEditor: PropTypes.bool,
});

export const ResourceLink = PropTypes.shape({
    source: PropTypes.shape({
        resourceGroupUrl: PropTypes.string,
        url: PropTypes.string,
    }),
    target: PropTypes.shape({
        resourceGroupUrl: PropTypes.string,
        url: PropTypes.string,
    }),
    dirty: PropTypes.bool,
    lastCleanVersion: PropTypes.string,
    inferredDirtiness: PropTypes.arrayOf(
        PropTypes.shape({
            resource: Resource,
            lastCleanVersion: PropTypes.string,
        })
    ),
});

export const DepiModel = PropTypes.shape({
    expandState: PropTypes.number.isRequired,
    resourceGroups: PropTypes.arrayOf(ResourceGroup),
    resources: PropTypes.arrayOf(Resource),
    links: PropTypes.arrayOf(ResourceLink),
});

export const BlackboardModel = PropTypes.shape({
    resources: PropTypes.arrayOf(Resource),
    links: PropTypes.arrayOf(ResourceLink),
});

export const SelectionEntry = PropTypes.shape({
    isResourceGroup: PropTypes.bool,
    isLink: PropTypes.bool,
    inDepi: PropTypes.bool,
    onBlackboard: PropTypes.bool,
    isDirty: PropTypes.bool,
    dependsOnDirty: PropTypes.bool,
    entry: PropTypes.oneOfType([Resource, ResourceLink, ResourceGroup]),
});

export const LayoutOptsType = PropTypes.shape({
    headerHeight: PropTypes.number,
    leftMenuPanel: PropTypes.bool,
    sideMenuWidth: PropTypes.number,
    defaultSideMenuItemWidth: PropTypes.number,
    // topMenuHeight: PropTypes.number,
    // defaultTopMenuItemHeight: PropTypes.number,
});
