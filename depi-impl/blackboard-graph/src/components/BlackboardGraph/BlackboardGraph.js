/* eslint-disable no-restricted-syntax */
import PropTypes from 'prop-types';
import React, { useState, useMemo, useCallback, useEffect } from 'react';
import ReactFlow, {
    Background,
    BackgroundVariant,
    ReactFlowProvider,
    Controls,
    ControlButton,
    MarkerType,
} from 'reactflow';
import ELK from 'elkjs';
// styles
import 'reactflow/dist/style.css';
import './styles.css';
// @mui
import {
    Margin as MarginIcon,
    MultipleStop as MultipleStopIcon,
    UnfoldLess as UnfoldLessIcon,
    UnfoldMore as UnfoldMoreIcon,
} from '@mui/icons-material';
// components
import NodeTypes from './NodeTypes';
import LinkEdge from './LinkEdge';
import AggregateEdge from './AggregateEdge';
import Markers from './Markers';
import ConnectionLine from './ConnectionLine';
// util
import DIMENSIONS from './DIMENSIONS';
import {
    getFullResourceId,
    getFullResourceGroupId,
    getResourceGroupIdFromId,
    getEdgeId,
    ABS_PATH_SUFFIX,
    isSameResource,
    isSameLink,
    isSameResourceGroup,
} from '../../utils';
import { expandResources, getParentIds } from './graphUtils';
// types
import { DepiModel, BlackboardModel, SelectionEntry } from '../../depiTypes';

const EdgeTypes = { LinkEdge, AggregateEdge };
const snapGrid = [10, 10];

BlackboardGraph.propTypes = {
    isReadOnly: PropTypes.bool,
    height: PropTypes.number,
    width: PropTypes.number,
    // toolsConfig: PropTypes.object,
    depiModel: DepiModel,
    blackboardModel: BlackboardModel,
    onExpandResourceGroups: PropTypes.func.isRequired,
    onCollapseResourceGroups: PropTypes.func.isRequired,
    selection: PropTypes.arrayOf(SelectionEntry).isRequired,
    setSelection: PropTypes.func.isRequired,
    onLinkResources: PropTypes.func.isRequired,
    showDirtyness: PropTypes.bool,
};

export default function BlackboardGraph({
    isReadOnly,
    depiModel,
    blackboardModel,
    onExpandResourceGroups,
    onCollapseResourceGroups,
    height,
    width,
    showDirtyness,
    selection,
    setSelection,
    onLinkResources,
}) {
    const [resourceGroupLayoutData, setResourceGroupLayoutData] = useState({});
    const [showAggregateLinks, setShowAggregateLinks] = useState(false);
    const [, setPendingExpand] = useState(null);
    // <toolId#rgUrl>: {
    //   orientation: 'left'/'right',
    //   position: {x: number, y: number},
    //   dimensions: {width: number, height: number}
    // }
    const [expanded, setExpanded] = useState({});
    const setNodeExpanded = useCallback((nodeOrNodeIds, expand, propagate) => {
        setExpanded((prevExpanded) => {
            const newExpanded = { ...prevExpanded };
            const nodeIds = nodeOrNodeIds instanceof Array ? nodeOrNodeIds : [nodeOrNodeIds];

            for (const nodeId of nodeIds) {
                newExpanded[nodeId] = expand;
                if (propagate) {
                    Object.keys(newExpanded).forEach((id) => {
                        if (id.startsWith(nodeId)) {
                            newExpanded[id] = expand;
                        }
                    });
                }
            }

            return newExpanded;
        });
    }, []);

    const onSwitchOrientation = useCallback(
        (id, orientation) => {
            const newResourceGroupLayoutData = { ...resourceGroupLayoutData };

            if (!newResourceGroupLayoutData[id]) {
                newResourceGroupLayoutData[id] = {};
            } else {
                newResourceGroupLayoutData[id] = { ...newResourceGroupLayoutData[id] };
            }

            newResourceGroupLayoutData[id].orientation = orientation;

            setResourceGroupLayoutData(newResourceGroupLayoutData);
        },
        [resourceGroupLayoutData]
    );

    useEffect(() => {
        setExpanded((prevExpanded) => {
            const dt = Date.now();
            const newExpanded = { ...prevExpanded };
            const resourceGroups = new Map();
            for (const resourceGroup of depiModel.resourceGroups) {
                const id = getFullResourceGroupId(resourceGroup);
                resourceGroups.set(id, resourceGroup);
                if (!Object.hasOwn(newExpanded, id)) {
                    newExpanded[id] = false;
                }
            }

            expandResources(depiModel.resources, resourceGroups, ({ id }) => {
                if (!Object.hasOwn(newExpanded, id)) {
                    newExpanded[id] = false;
                }
            });

            // When one resource is selected - make sure it is displayed.
            // But only if it's not on the blackboard (if it is then it's already displayed).
            if (selection.length === 1 && selection[0].isLink === false && !selection[0].onBlackboard) {
                const resource = selection[0].entry;
                const resourceGroupId = getFullResourceGroupId({
                    toolId: resource.toolId,
                    url: resource.resourceGroupUrl,
                });

                const resourceGroup = resourceGroups.get(resourceGroupId);
                if (!resourceGroup) {
                    console.log('resourceGroups not loaded - will not expand selected.');
                } else if (!resourceGroup.isActiveInEditor) {
                    console.log('resourceGroup not active - will not expand selected.');
                } else {
                    const { parentRootId, pathPieces, pathDivider } = getParentIds(resource, resourceGroup);

                    newExpanded[resourceGroupId] = true;
                    let parentId = parentRootId;
                    for (const pathSegment of pathPieces) {
                        parentId = `${parentId}${pathSegment}${pathDivider}`;
                        newExpanded[parentId] = true;
                    }
                }
            }

            console.log('calculating expanded', Date.now() - dt, '[ms]');
            return newExpanded;
        });
    }, [depiModel, selection]);

    const [nodes, edges] = useMemo(() => {
        const dt = Date.now();
        const resourceGroupNodes = new Map();

        depiModel.resourceGroups.forEach((resourceGroup) => {
            const id = getFullResourceGroupId(resourceGroup);
            resourceGroupNodes.set(id, {
                id,
                type: 'ResourceGroupNode',
                draggable: true,
                dragHandle: '.depi-drag-handle',
                data: {
                    resourceGroup,
                    orientation: 'left',
                    width: 0,
                    height: 0,
                    childrenDepth: 0,
                    isExpanded: expanded[id],
                    inDepi: true,
                    setNodeExpanded: (nodeId, expand, propagate) => {
                        if (expand) {
                            onExpandResourceGroups([{ toolId: resourceGroup.toolId, url: resourceGroup.url }]);
                            setPendingExpand({ nodeId, expand, propagate });
                        } else {
                            onCollapseResourceGroups([{ toolId: resourceGroup.toolId, url: resourceGroup.url }]);
                            setNodeExpanded(nodeId, expand, propagate);
                        }
                    },
                },
                position: { x: 0, y: 0 }, // Will be decided at the very end.
                // Temporary prop
                children: new Map(), // Tree-like structure of nodes
            });
        });

        const dirtyResourcesFullUrls = new Set();
        const dirtyDependersFullUrls = new Set();
        depiModel.links.forEach((link) => {
            if (link.dirty) {
                dirtyResourcesFullUrls.add(getFullResourceId(link.target));
                dirtyDependersFullUrls.add(getFullResourceId(link.source));
            }

            if (link.inferredDirtiness.length > 0) {
                dirtyDependersFullUrls.add(getFullResourceId(link.source));
            }

            link.inferredDirtiness.forEach(({ resource }) => {
                dirtyResourcesFullUrls.add(getFullResourceId(resource));
            });
        });

        [...depiModel.resources]
            .sort((a, b) => a.url.length - b.url.length)
            .forEach((resource) => {
                const resourceGroupId = getFullResourceGroupId({
                    toolId: resource.toolId,
                    url: resource.resourceGroupUrl,
                });
                const resourceGroupNode = resourceGroupNodes.get(resourceGroupId);
                if (!resourceGroupNode.data.isExpanded) {
                    // Resource group is not expanded skip node.
                    return;
                }

                const { resourceGroup } = resourceGroupNode.data;
                // TODO: Use graphUtils here.
                const pathPieces = resource.url.split(resourceGroup.pathDivider);
                const isContainerResource = resource.url.endsWith(resourceGroup.pathDivider);
                if (pathPieces[0] === '') {
                    pathPieces.shift();
                }

                if (isContainerResource) {
                    pathPieces.pop();
                }

                let id = [resourceGroup.toolId, resourceGroup.url, resourceGroup.pathDivider].join(ABS_PATH_SUFFIX);
                let parent = resourceGroupNode;

                for (let i = 0; i < pathPieces.length; i += 1) {
                    if (i > 0) {
                        if (!expanded[id]) {
                            // Parent is not expaned -> not displayed.
                            return;
                        }
                    }

                    if (!parent.children.has(pathPieces[i])) {
                        // All container nodes will end with /.
                        const childId = `${id}${pathPieces[i]}${resourceGroup.pathDivider}`;
                        parent.children.set(pathPieces[i], {
                            id: childId,
                            type: 'ContainerNode',
                            draggable: false,
                            parentNode: i === 0 ? resourceGroupNode.id : id,
                            extent: 'parent',
                            data: {
                                label: pathPieces[i],
                                resourceGroupId,
                                childrenDepth: 0,
                                showDirtyness,
                                isContainer: true,
                                isExpanded: expanded[childId],
                                setNodeExpanded,
                            },
                            // Temporary prop
                            children: new Map(),
                        });
                    }

                    parent = parent.children.get(pathPieces[i]);
                    ({ id } = parent);
                }

                // After last iteration we are at the actual resource.
                const resourceNode = parent;
                resourceNode.id = getFullResourceId(resource);
                resourceNode.data.resource = resource;
                resourceNode.data.inDepi = true;
                resourceNode.type = 'ResourceNode';
                resourceNode.data.label = resource.name;
                if (isContainerResource) {
                    resourceNode.data.label += resourceGroup.pathDivider;
                    resourceNode.data.isContainer = true;
                    // Virtual containers do not end with /
                    resourceNode.data.isExpanded = expanded[resourceNode.id];
                } else {
                    resourceNode.data.isContainer = false;
                }

                if (dirtyResourcesFullUrls.has(getFullResourceId(resource))) {
                    resourceNode.data.isDirty = true;
                }

                if (dirtyDependersFullUrls.has(getFullResourceId(resource))) {
                    resourceNode.data.dependsOnDirty = true;
                }
            });

        const nodes = new Map();

        function calculateChildrenDepth(node) {
            node.data.childrenDepth = 0;
            if (node.children.length === 0) {
                return 0;
            }

            node.children.forEach((childNode) => {
                const childDepth = calculateChildrenDepth(childNode);
                node.data.childrenDepth = Math.max(childDepth + 1, node.data.childrenDepth);
            });

            // console.log('depth', node.data.childrenDepth, node.id);
            return node.data.childrenDepth;
        }

        function assignDimensionsRec(node, yPos, depth, orientation) {
            nodes.set(node.id, node);
            const { RESOURCE_GROUP, CONTAINER, RESOURCE } = DIMENSIONS;
            const PARENT_DIM = depth === 1 ? RESOURCE_GROUP : CONTAINER;

            if (node.data.isContainer || node.type === 'ResourceGroupNode') {
                node.data.width =
                    node.data.childrenDepth * (CONTAINER.LEFT_PADDING + CONTAINER.RIGHT_PADDING) + RESOURCE.WIDTH;
                node.data.height = CONTAINER.TOP_PADDING;

                if (node.type === 'ResourceGroupNode') {
                    node.data.height = RESOURCE_GROUP.TOP_PADDING;
                    if (node.data.childrenDepth === 0) {
                        node.data.width += CONTAINER.LEFT_PADDING + CONTAINER.RIGHT_PADDING;
                    }
                }

                // Order children with containers first and then by name.
                const children = [...node.children.values()].sort((a, b) => {
                    if (a.data.isContainer && !b.data.isContainer) {
                        return -1;
                    }

                    if (!a.data.isContainer && b.data.isContainer) {
                        return 1;
                    }

                    return a.data.label.localeCompare(b.data.label);
                });

                children.forEach((child) => {
                    const containsNodes = child.data.isContainer && child.children.size > 0;
                    node.data.height += assignDimensionsRec(child, node.data.height, depth + 1, orientation);

                    if (containsNodes) {
                        node.data.height += CONTAINER.VERTICAL_SPACE;
                    } else {
                        node.data.height += RESOURCE.VERTICAL_SPACE;
                    }
                });
            } else {
                node.data.width = RESOURCE.WIDTH;
                node.data.height = RESOURCE.HEIGHT;
                node.data.orientation = orientation;
            }

            node.position = {
                x: PARENT_DIM.LEFT_PADDING,
                y: yPos,
            };

            delete node.children;

            // eslint-disable-next-line no-restricted-syntax

            return node.data.height;
        }

        let i = 0;
        let orientation = 'left';
        const layoutData = { ...resourceGroupLayoutData };
        let layoutDataChanged = false;

        [...resourceGroupNodes.values()]
            .sort((rg1, rg2) => rg1.data.resourceGroup.name.localeCompare(rg2.data.resourceGroup.name))
            .forEach((rg) => {
                let rgLayout = layoutData[rg.id];

                if (!rgLayout) {
                    layoutDataChanged = true;
                    rgLayout = {};
                    layoutData[rg.id] = rgLayout;
                }

                if (!rgLayout.orientation) {
                    layoutDataChanged = true;
                    rgLayout.orientation = orientation;
                    orientation = i % 2 === 0 ? 'right' : 'left';
                }

                if (!rgLayout.position) {
                    layoutDataChanged = true;
                    const xPertubation = i % 4 < 2 ? 0 : 80;
                    rgLayout.position = {
                        y: (i - (i % 2)) * 60,
                        x: (i % 2) * 400 + xPertubation + i * 10,
                    };
                    i += 1;
                }

                rg.data.orientation = rgLayout.orientation;
                calculateChildrenDepth(rg);
                assignDimensionsRec(rg, 0, 0, rg.data.orientation);
                rg.position.x = rgLayout.position.x;
                rg.position.y = rgLayout.position.y;
                if (
                    !rgLayout.dimensions ||
                    rgLayout.dimensions.width !== rg.data.width ||
                    rgLayout.dimensions.height !== rg.data.height
                ) {
                    layoutDataChanged = true;
                    rgLayout.dimensions = { width: rg.data.width, height: rg.data.height };
                }
            });

        const edges = new Map();
        depiModel.links.forEach((link) => {
            const { source, target } = link;

            function getFirstParentId(id, resource) {
                const rgId = getFullResourceGroupId({ toolId: resource.toolId, url: resource.resourceGroupUrl });
                const { pathDivider } = resourceGroupNodes.get(rgId).data.resourceGroup;
                let parentId = id;

                while (!nodes.has(parentId)) {
                    parentId = parentId.endsWith(pathDivider) ? parentId.substring(0, parentId.length - 1) : parentId;
                    if (parentId.endsWith(ABS_PATH_SUFFIX)) {
                        // We've reached the resource-group.
                        return rgId;
                    }

                    parentId = parentId.substring(0, parentId.lastIndexOf(pathDivider) + 1);
                }

                return parentId;
            }

            let sourceId = getFullResourceId(source);
            let targetId = getFullResourceId(target);
            let isAggregate = false;
            if (!nodes.has(sourceId) && !nodes.has(targetId) && !showAggregateLinks) {
                return;
            }

            if (!nodes.has(sourceId)) {
                sourceId = getFirstParentId(sourceId, source);
                isAggregate = true;
            }

            if (!nodes.has(targetId)) {
                targetId = getFirstParentId(targetId, target);
                isAggregate = true;
            }

            const edgeId = getEdgeId(sourceId, targetId);

            if (!isAggregate) {
                edges.set(edgeId, {
                    id: edgeId,
                    type: 'LinkEdge',
                    animated: false,
                    data: {
                        link,
                        inDepi: true,
                        showDirtyness,
                    },
                    source: sourceId,
                    target: targetId,
                    markerEnd: {
                        type: MarkerType.Arrow,
                        width: 15,
                        height: 15,
                    },
                });
                return;
            }

            if (!edges.has(edgeId)) {
                edges.set(edgeId, {
                    id: edgeId,
                    type: 'AggregateEdge',
                    animated: false,
                    data: {
                        links: [],
                        showDirtyness,
                    },
                    source: sourceId,
                    target: targetId,
                    markerEnd: {
                        type: MarkerType.Arrow,
                        width: 10,
                        height: 10,
                    },
                });
            }

            edges.get(edgeId).data.links.push(link);
        });

        console.log('calculating nodes and edges', Date.now() - dt, '[ms]');

        if (layoutDataChanged) {
            setResourceGroupLayoutData(layoutData);
        }

        return [[...nodes.values()], [...edges.values()]];
        // We don't want to react on resourceGroupPositions - only use the latest when the depiModel changes.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [depiModel, showDirtyness, setNodeExpanded, expanded, showAggregateLinks]);

    const [augmentedNodes, augmentedEdges] = useMemo(() => {
        const dt = Date.now();
        const augmentedNodes = [...nodes];
        const augmentedEdges = [...edges];

        // We need to keep track of any changed dimensions of the resource-groups. They can change when a new resource
        // is added to the black-board or from updates to the state-var resourceGroupPositions
        const resourceGroupNodes = augmentedNodes.filter((node) => node.type === 'ResourceGroupNode');
        const resourceGroupNodesCopies = {};
        let pureBlackboardRgCnt = 0;
        const layoutsForNewResourceGroups = new Map();
        const getResourceGroupNodeCopy = (rgId, resource) => {
            let rgNode;
            if (resourceGroupNodesCopies[rgId]) {
                rgNode = resourceGroupNodesCopies[rgId];
            } else {
                const rgOriginal = resourceGroupNodes.find((rg) => rg.id === rgId);
                if (rgOriginal) {
                    rgNode = { ...rgOriginal };
                    rgNode.data = { ...rgNode.data };
                    rgNode.position = { ...rgNode.position };
                } else {
                    let orientation;
                    let position;
                    let dimensions;

                    const storedLayout = resourceGroupLayoutData[rgId];
                    if (storedLayout) {
                        ({ orientation, position, dimensions } = storedLayout);
                    } else {
                        orientation = pureBlackboardRgCnt % 2 === 0 ? 'left' : 'right';
                        position = { x: -50 + pureBlackboardRgCnt * 200, y: -100 + pureBlackboardRgCnt * 200 };
                        dimensions = {
                            width:
                                DIMENSIONS.RESOURCE_GROUP.LEFT_PADDING +
                                DIMENSIONS.RESOURCE.WIDTH +
                                DIMENSIONS.RESOURCE_GROUP.RIGHT_PADDING,
                            height: DIMENSIONS.RESOURCE_GROUP.TOP_PADDING,
                        };

                        layoutsForNewResourceGroups.set(rgId, { orientation, position, dimensions });
                    }

                    rgNode = {
                        id: getFullResourceGroupId({ toolId: resource.toolId, url: resource.resourceGroupUrl }),
                        type: 'ResourceGroupNode',
                        draggable: true,
                        dragHandle: '.depi-drag-handle',
                        data: {
                            orientation,
                            resourceGroup: {
                                name: resource.resourceGroupName,
                                url: resource.resourceGroupUrl,
                                toolId: resource.toolId,
                                version: resource.resourceGroupVersion,
                                isActiveInEditor: true, // Pure black-board resource-group so all nodes available.
                            },
                            onBlackboard: true,
                            width: dimensions.width,
                            height: dimensions.height,
                            onSwitchOrientation,
                        },
                        position,
                    };
                    pureBlackboardRgCnt += 1;
                    resourceGroupNodes.push(rgNode);
                    augmentedNodes.push(rgNode);
                }

                resourceGroupNodesCopies[rgId] = rgNode;
            }

            return rgNode;
        };

        // Check if any layout for the resourceGroups changed.
        resourceGroupNodes.forEach((rg) => {
            const storedLayout = resourceGroupLayoutData[rg.id];
            const rgNode = getResourceGroupNodeCopy(rg.id);
            rgNode.data.onSwitchOrientation = onSwitchOrientation;

            if (!storedLayout) {
                return;
            }

            const storedPosition = resourceGroupLayoutData[rg.id].position;
            if (storedPosition && (storedPosition.x !== rg.position.x || storedPosition.y !== rg.position.y)) {
                rgNode.position = storedPosition;
            }

            if (storedLayout.orientation && storedLayout.orientation !== rg.data.orientation) {
                rgNode.data.orientation = storedLayout.orientation;
            }

            if (storedLayout.orientation) {
                augmentedNodes.forEach((node, idx) => {
                    const { resourceGroupId } = node.data;
                    if (
                        resourceGroupId &&
                        resourceGroupId === rg.id &&
                        augmentedNodes[idx].data.orientation !== storedLayout.orientation
                    ) {
                        augmentedNodes[idx] = { ...augmentedNodes[idx] };
                        augmentedNodes[idx].data = { ...augmentedNodes[idx].data };
                        augmentedNodes[idx].data.orientation = storedLayout.orientation;
                    }
                });
            }
        });

        blackboardModel.resources.forEach((resource) => {
            const idx = augmentedNodes.findIndex((n) => isSameResource(resource, n.data.resource));
            if (idx > -1) {
                if (augmentedNodes[idx].data.onBlackboard) {
                    // Node already added..
                    return;
                }

                augmentedNodes[idx] = { ...augmentedNodes[idx] };
                augmentedNodes[idx].data = { ...augmentedNodes[idx].data };
                augmentedNodes[idx].data.onBlackboard = true;
                return;
            }

            const resourceGroupId = getFullResourceGroupId({ toolId: resource.toolId, url: resource.resourceGroupUrl });
            const rgNode = getResourceGroupNodeCopy(resourceGroupId, resource);

            augmentedNodes.push({
                id: getFullResourceId(resource),
                type: 'ResourceNode',
                parentNode: resourceGroupId,
                extent: 'parent',
                position: {
                    x: DIMENSIONS.RESOURCE_GROUP.LEFT_PADDING,
                    y: rgNode.data.height,
                },
                data: {
                    label: resource.url,
                    resourceGroupId,
                    resource,
                    onBlackboard: true,
                    inDepi: false,
                    orientation: rgNode.data.orientation,
                    width: DIMENSIONS.RESOURCE.WIDTH,
                    height: DIMENSIONS.RESOURCE.HEIGHT,
                },
            });

            rgNode.data.height += DIMENSIONS.RESOURCE.VERTICAL_SPACE + DIMENSIONS.RESOURCE.HEIGHT;
        });

        blackboardModel.links.forEach((link) => {
            const { source, target } = link;
            const sourceId = getFullResourceId(source);
            const targetId = getFullResourceId(target);
            const edgeId = getEdgeId(sourceId, targetId);

            const idx = augmentedEdges.findIndex((e) => e.id === edgeId);

            if (idx > 0) {
                if (augmentedEdges[idx].data.onBlackboard) {
                    // Edge already added..
                    return;
                }

                augmentedEdges[idx] = { ...augmentedEdges[idx] };
                augmentedEdges[idx].data = { ...augmentedEdges[idx].data };
                augmentedEdges[idx].data.onBlackboard = true;
                return;
            }

            augmentedEdges.push({
                id: edgeId,
                type: 'LinkEdge',
                source: sourceId,
                target: targetId,
                markerEnd: {
                    type: MarkerType.Arrow,
                    width: 15,
                    height: 15,
                },
                data: {
                    inDepi: false,
                    onBlackboard: true,
                    link,
                },
            });
        });

        Object.keys(resourceGroupNodesCopies).forEach((rgId) => {
            const idx = augmentedNodes.findIndex((n) => n.id === rgId);
            if (idx > -1) {
                augmentedNodes[idx] = resourceGroupNodesCopies[rgId];
            }
        });

        selection.forEach(({ isResourceGroup, isLink, entry }) => {
            if (isResourceGroup) {
                const idx = augmentedNodes.findIndex((node) => isSameResourceGroup(node.data.resourceGroup, entry));
                if (idx > -1) {
                    augmentedNodes[idx] = { ...augmentedNodes[idx] };
                    augmentedNodes[idx].selected = true;
                }
            } else if (isLink) {
                const idx = augmentedEdges.findIndex((edge) => isSameLink(edge.data.link, entry));
                if (idx > -1) {
                    augmentedEdges[idx] = { ...augmentedEdges[idx] };
                    augmentedEdges[idx].selected = true;
                }
            } else {
                const idx = augmentedNodes.findIndex((node) => isSameResource(node.data.resource, entry));
                if (idx > -1) {
                    augmentedNodes[idx] = { ...augmentedNodes[idx] };
                    augmentedNodes[idx].selected = true;
                }
            }
        });

        if (layoutsForNewResourceGroups.size > 0) {
            setResourceGroupLayoutData((currLayoutData) => {
                const newLayoutData = { ...currLayoutData };
                for (const [id, layoutData] of layoutsForNewResourceGroups) {
                    newLayoutData[id] = layoutData;
                }

                return newLayoutData;
            });
        }

        console.log('calculating augmented nodes and edges', Date.now() - dt, '[ms]');
        return [augmentedNodes, augmentedEdges];
    }, [nodes, edges, blackboardModel, resourceGroupLayoutData, selection, onSwitchOrientation]);

    const allResourceGroupsExpanded = useMemo(
        () => !depiModel.resourceGroups.some((rg) => !rg.isActiveInEditor),
        [depiModel.resourceGroups]
    );

    // Make sure resource-groups do not overlap

    useEffect(() => {
        const dims = Object.keys(resourceGroupLayoutData).map((id) => ({
            id,
            xMin: resourceGroupLayoutData[id].position.x,
            xMax: resourceGroupLayoutData[id].position.x + resourceGroupLayoutData[id].dimensions.width,
            yMin: resourceGroupLayoutData[id].position.y,
            yMax: resourceGroupLayoutData[id].position.y + resourceGroupLayoutData[id].dimensions.height,
        }));

        for (let i = 0; i < dims.length - 1; i += 1) {
            const node = dims[i];
            for (let j = i + 1; j < dims.length; j += 1) {
                const otherNode = dims[j];
                const overlaps =
                    node.xMax >= otherNode.xMin &&
                    otherNode.xMax >= node.xMin &&
                    node.yMax >= otherNode.yMin &&
                    otherNode.yMax >= node.yMin;

                if (overlaps) {
                    let rgId = node.id;
                    let y = otherNode.yMax + 20;
                    let x = node.xMin;
                    if (node.yMin < otherNode.yMin) {
                        rgId = otherNode.id;
                        y = node.yMax + 20;
                        x = otherNode.xMin;
                    }

                    console.log(rgId, x, y);

                    setResourceGroupLayoutData((prevLayout) => {
                        const newLayout = { ...prevLayout };
                        newLayout[rgId] = { ...newLayout[rgId] };
                        newLayout[rgId].position = { x, y };
                        return newLayout;
                    });

                    return;
                }
            }
        }
    }, [resourceGroupLayoutData]);

    useEffect(() => {
        setPendingExpand((expandInfo) => {
            console.log('PendingExpand at depi-expandState', depiModel.expandState, expandInfo);
            if (!expandInfo) {
                return expandInfo;
            }

            setNodeExpanded(expandInfo.nodeId, expandInfo.expand, expandInfo.propagate);
            return null;
        });
    }, [depiModel.expandState, setNodeExpanded]);

    // --------------------- Event handlers on graph actions ------------------------
    const onConnect = useCallback(
        (eventData) => {
            const { source, target } = eventData;
            const edgeId = getEdgeId(source, target);

            if (augmentedEdges.some((edgeData) => edgeData.id === edgeId)) {
                alert('Already connected');
                return;
            }

            let sourceResource = null;
            let targetResource = null;

            for (const node of augmentedNodes) {
                if (node.id === source) {
                    sourceResource = node.data.resource;
                    if (targetResource) {
                        break;
                    }
                }

                if (node.id === target) {
                    targetResource = node.data.resource;
                    if (sourceResource) {
                        break;
                    }
                }
            }

            if (!sourceResource || !targetResource) {
                console.error('Source- and/or target-node missing in nodes..');
                return;
            }

            onLinkResources(sourceResource, targetResource);
        },
        [augmentedNodes, augmentedEdges, onLinkResources]
    );

    const onNodesChange = useCallback(
        (events) => {
            const positionEvents = events.filter((event) => event.type === 'position' && event.position);

            if (positionEvents.length === 0) {
                return;
            }

            const newResourceGroupLayoutData = { ...resourceGroupLayoutData };

            positionEvents.forEach((event) => {
                const { id, position } = event;
                if (!newResourceGroupLayoutData[id]) {
                    newResourceGroupLayoutData[id] = {};
                } else {
                    newResourceGroupLayoutData[id] = { ...newResourceGroupLayoutData[id] };
                }

                newResourceGroupLayoutData[id].position = position;
            });

            setResourceGroupLayoutData(newResourceGroupLayoutData);
        },
        [resourceGroupLayoutData]
    );

    const addToSelection = useCallback(
        (newEntries, ctrlKey) => {
            setSelection((prevSelection) => {
                if (!newEntries || newEntries.length === 0) {
                    return prevSelection.length > 0 ? [] : prevSelection;
                }

                function compareEntry(theEntry) {
                    return ({ isResourceGroup, isLink, entry }) => {
                        if (theEntry.isResourceGroup && isResourceGroup) {
                            return isSameResourceGroup(entry, theEntry.entry);
                        }

                        if (theEntry.isLink && isLink) {
                            return isSameLink(entry, theEntry.entry);
                        }

                        if (!theEntry.isLink && !isLink && !theEntry.isResourceGroup && !isResourceGroup) {
                            return isSameResource(entry, theEntry.entry);
                        }

                        return false;
                    };
                }

                if (ctrlKey) {
                    const newSelection = [...prevSelection];
                    for (const newEntry of newEntries) {
                        const idx = newSelection.findIndex(compareEntry(newEntry));

                        if (idx > -1) {
                            newSelection.splice(idx, 1);
                        } else {
                            newSelection.push(newEntry);
                        }
                    }

                    return newSelection;
                }

                if (
                    newEntries.length === 1 &&
                    prevSelection.length === 1 &&
                    prevSelection.some(compareEntry(newEntries[0]))
                ) {
                    return [];
                }

                return newEntries;
            });
        },
        [setSelection]
    );

    const onNodeClick = useCallback(
        (event, node) => {
            if (node.type === 'ResourceGroupNode') {
                addToSelection(
                    [
                        {
                            isResourceGroup: true,
                            inDepi: node.data.inDepi,
                            onBlackboard: node.data.onBlackboard,
                            entry: node.data.resourceGroup,
                        },
                    ],
                    false
                );
                return;
            }

            if (node.type !== 'ResourceNode') {
                addToSelection(null);
                return;
            }

            addToSelection(
                [
                    {
                        isLink: false,
                        inDepi: node.data.inDepi,
                        onBlackboard: node.data.onBlackboard,
                        entry: node.data.resource,
                        isDirty: node.data.isDirty,
                        dependsOnDirty: node.data.dependsOnDirty,
                    },
                ],
                event.ctrlKey
            );
        },
        [addToSelection]
    );

    const onEdgeClick = useCallback(
        (event, edge) => {
            // console.log(edge.id);
            if (edge.type === 'LinkEdge') {
                addToSelection(
                    [
                        {
                            isLink: true,
                            inDepi: edge.data.inDepi,
                            onBlackboard: edge.data.onBlackboard,
                            entry: edge.data.link,
                        },
                    ],
                    event.ctrlKey
                );
            } else if (edge.type === 'AggregateEdge') {
                addToSelection(
                    edge.data.links.map((link) => ({
                        isLink: true,
                        inDepi: true,
                        onBlackboard: false,
                        entry: link,
                    })),
                    event.ctrlKey
                );
            }
        },
        [addToSelection]
    );

    const onPaneClick = useCallback(() => {
        setSelection((prevSelection) => (prevSelection.length > 0 ? [] : prevSelection));
    }, [setSelection]);

    const isValidConnection = useCallback(({ source, target }) => source !== target, []);

    const expandCollapseAll = useCallback(
        (expand) => {
            const rgRefs = depiModel.resourceGroups.map((rg) => ({ toolId: rg.toolId, url: rg.url }));

            if (expand) {
                const toExpand = depiModel.resourceGroups
                    .filter((rg) => !rg.isActiveInEditor)
                    .map((rg) => ({ toolId: rg.toolId, url: rg.url }));

                if (toExpand.length > 0) {
                    onExpandResourceGroups(toExpand);
                    setPendingExpand({
                        nodeId: rgRefs.map((rgRef) => getFullResourceGroupId(rgRef)),
                        expand,
                        propagate: true,
                    });
                }
            } else {
                const toCollapse = depiModel.resourceGroups
                    .filter((rg) => rg.isActiveInEditor)
                    .map((rg) => ({ toolId: rg.toolId, url: rg.url }));

                if (toCollapse.length > 0) {
                    onCollapseResourceGroups(toCollapse);
                    setNodeExpanded(
                        rgRefs.map((rgRef) => getFullResourceGroupId(rgRef)),
                        expand,
                        true
                    );
                }
            }
        },
        [depiModel.resourceGroups, onExpandResourceGroups, onCollapseResourceGroups, setNodeExpanded]
    );

    const runAutoLayout = () => {
        const elk = new ELK();

        const rgNodes = augmentedNodes.filter((node) => node.type === 'ResourceGroupNode');

        const children = rgNodes.map((node) => ({
            id: node.id,
            width: node.data.width > 180 ? node.data.width : 180,
            height: node.data.height,
        }));
        const edges = augmentedEdges.map((edge) => {
            console.log(edge);

            return {
                id: edge.id,
                sources: [getResourceGroupIdFromId(edge.source)],
                targets: [getResourceGroupIdFromId(edge.target)],
            };
        });

        console.log(edges);
        const graph = {
            id: 'root',
            layoutOptions: { 'elk.algorithm': 'layered' },
            children,
            edges,
        };
        console.log('Is this');
        elk.layout(graph)
            .then((layout) => {
                console.log(resourceGroupLayoutData);
                console.log(layout);
                const newResourceGroupLayoutData = { ...resourceGroupLayoutData };
                layout.children.forEach(({ id, x, y }) => {
                    if (!newResourceGroupLayoutData[id]) {
                        newResourceGroupLayoutData[id] = {};
                    } else {
                        newResourceGroupLayoutData[id] = { ...newResourceGroupLayoutData[id] };
                    }

                    newResourceGroupLayoutData[id].position = { x, y };
                });

                setResourceGroupLayoutData(newResourceGroupLayoutData);
            })
            .catch(console.error);
        console.log('async?');
    };

    if (!width || !height) {
        return <div />;
    }

    return (
        <>
            <div style={{ width, height }}>
                <ReactFlowProvider>
                    <Markers />
                    <ReactFlow
                        snapToGrid
                        fitView
                        nodesConnectable={!isReadOnly}
                        onNodesChange={onNodesChange}
                        nodes={augmentedNodes}
                        edges={augmentedEdges}
                        nodeTypes={NodeTypes}
                        edgeTypes={EdgeTypes}
                        connectionLineComponent={ConnectionLine}
                        isValidConnection={isValidConnection}
                        snapGrid={snapGrid}
                        onNodeClick={onNodeClick}
                        onEdgeClick={onEdgeClick}
                        onPaneClick={onPaneClick}
                        onConnect={isReadOnly ? () => {} : onConnect}
                    >
                        <Background id="1" gap={10} color="#f1f1f1" variant={BackgroundVariant.Lines} />
                        <Controls position="bottom-left" showInteractive={false}>
                            <ControlButton
                                title={`${allResourceGroupsExpanded ? 'collapse' : 'expand'} all resource groups`}
                                onClick={() => {
                                    expandCollapseAll(!allResourceGroupsExpanded);
                                }}
                            >
                                {allResourceGroupsExpanded ? <UnfoldLessIcon /> : <UnfoldMoreIcon />}
                            </ControlButton>

                            <ControlButton title={'Run auto-layout'} onClick={runAutoLayout}>
                                <MarginIcon />
                            </ControlButton>
                            <ControlButton
                                title={'Toggle show aggregate links'}
                                onClick={() => setShowAggregateLinks((prev) => !prev)}
                            >
                                <MultipleStopIcon color={showAggregateLinks ? 'primary' : undefined} />
                            </ControlButton>
                        </Controls>
                    </ReactFlow>
                </ReactFlowProvider>
            </div>
        </>
    );
}
