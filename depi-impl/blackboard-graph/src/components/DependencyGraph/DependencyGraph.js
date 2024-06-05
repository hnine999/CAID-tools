import PropTypes from 'prop-types';
import React, { useState, useEffect, useCallback } from 'react';
import ReactFlow, { ReactFlowProvider, Controls } from 'reactflow';
// components
import DependencyResourceNode from './DependencyResourceNode';
import DependencyLinkEdge from './DependencyLinkEdge';
import Markers from '../BlackboardGraph/Markers';
// util
import { getLayoutedElements } from './graphUtils';
import { getFullResourceId, getEdgeId, isSameLink, isSameResource } from '../../utils';
import { ResourceRef, ResourceLink, SelectionEntry } from '../../depiTypes';

const HEIGHT = 100;
const WIDTH = 160;
const NodeTypes = { DependencyResourceNode };
const EdgeTypes = { DependencyLinkEdge };

DependencyGraph.propTypes = {
    resource: ResourceRef,
    links: PropTypes.arrayOf(ResourceLink),
    isReadOnly: PropTypes.bool,
    width: PropTypes.number,
    height: PropTypes.number,
    showDirtyness: PropTypes.bool,
    selection: PropTypes.arrayOf(SelectionEntry).isRequired,
    setSelection: PropTypes.func.isRequired,
};

export default function DependencyGraph({
    isReadOnly,
    width,
    height,
    showDirtyness,
    resource,
    links,
    selection,
    setSelection,
}) {
    const [nodes, setNodes] = useState([]);
    const [edges, setEdges] = useState([]);

    useEffect(() => {
        const edges = [];
        const nodes = new Map();

        if (!resource) {
            setNodes(nodes);
            setEdges(edges);
            return;
        }

        const starResourceId = getFullResourceId(resource);

        function addNode(id, resource) {
            nodes.set(id, {
                id,
                position: { x: 0, y: 0 },
                type: 'DependencyResourceNode',
                data: {
                    isStartResource: id === starResourceId,
                    isReadOnly,
                    resource,
                    width: WIDTH,
                    height: HEIGHT,
                },
            });
        }

        addNode(starResourceId, resource);

        links.forEach((link) => {
            const sourceId = getFullResourceId(link.source);
            const targetId = getFullResourceId(link.target);
            if (!nodes.has(sourceId)) {
                addNode(sourceId, link.source, link);
            }
            if (!nodes.has(targetId)) {
                addNode(targetId, link.target, link);
            }

            edges.push({
                id: getEdgeId(sourceId, targetId),
                type: 'DependencyLinkEdge',
                source: sourceId,
                target: targetId,
                data: {
                    link,
                    isReadOnly,
                    showDirtyness,
                },
            });
        });

        nodes.forEach((n) => {
            n.data.width = WIDTH;
            n.data.height = HEIGHT;
        });

        const nodeArr = [...nodes.values()];
        getLayoutedElements(nodeArr, edges, 'LR');

        edges.forEach((edge) => {
            const sourceNode = nodes.get(edge.source);
            const targetNode = nodes.get(edge.target);
            const targetIsToTheLeft = targetNode.position.x - sourceNode.position.x <= 0;

            if (targetIsToTheLeft) {
                edge.targetHandle = 'targetCircular';
            }
        });

        setNodes(nodeArr);
        setEdges(edges);
    }, [resource, links, isReadOnly, showDirtyness]);

    useEffect(() => {
        let newEdges = null;
        let newNodes = null;
        // New selection.
        selection.forEach(({ isLink, entry }) => {
            if (isLink) {
                const idx = edges.findIndex((edge) => isSameLink(edge.data.link, entry));
                if (idx > -1 && !edges[idx].selected) {
                    if (!newEdges) {
                        newEdges = [...edges];
                    }

                    newEdges[idx] = { ...newEdges[idx] };
                    newEdges[idx].selected = true;
                }
            } else {
                const idx = nodes.findIndex((node) => isSameResource(node.data.resource, entry));
                if (idx > -1 && !nodes[idx].selected) {
                    if (!newNodes) {
                        newNodes = [...nodes];
                    }

                    newNodes[idx] = { ...newNodes[idx] };
                    newNodes[idx].selected = true;
                }
            }
        });

        // Clearing out old selection.
        edges.forEach((edge, idx) => {
            if (edge.selected && !selection.some(({ isLink, entry }) => isLink && isSameLink(edge.data.link, entry))) {
                if (!newEdges) {
                    newEdges = [...edges];
                }
                newEdges[idx] = { ...newEdges[idx] };
                newEdges[idx].selected = false;
            }
        });

        nodes.forEach((node, idx) => {
            if (
                node.selected &&
                !selection.some(({ isLink, entry }) => !isLink && isSameResource(node.data.resource, entry))
            ) {
                if (!newNodes) {
                    newNodes = [...nodes];
                }
                newNodes[idx] = { ...newNodes[idx] };
                newNodes[idx].selected = false;
            }
        });

        if (newNodes) {
            setNodes(newNodes);
        }
        if (newEdges) {
            setEdges(newEdges);
        }
    }, [selection, nodes, edges]);

    const onNodeClick = useCallback(
        (_, node) => {
            if (selection.some(({ entry }) => isSameResource(node.data.resource, entry))) {
                // Already selected.
                return;
            }

            setSelection([{ isLink: false, inDepi: true, onBlackboard: false, entry: node.data.resource }]);
        },
        [selection, setSelection]
    );

    const onEdgeClick = useCallback(
        (_, edge) => {
            if (selection.some(({ entry }) => isSameLink(edge.data.link, entry))) {
                // Already selected.
                return;
            }

            setSelection([{ isLink: true, inDepi: true, onBlackboard: false, entry: edge.data.link }]);
        },
        [selection, setSelection]
    );

    const onPaneClick = useCallback(() => {
        if (selection.length > 0) {
            setSelection([]);
        }
    }, [selection, setSelection]);

    return (
        <div style={{ width, height }}>
            <ReactFlowProvider>
                <Markers />
                <ReactFlow
                    fitView
                    nodes={nodes}
                    edges={edges}
                    nodeTypes={NodeTypes}
                    edgeTypes={EdgeTypes}
                    onNodeClick={onNodeClick}
                    onEdgeClick={onEdgeClick}
                    onPaneClick={onPaneClick}
                >
                    <Controls position="bottom-left" showInteractive={false} />
                </ReactFlow>
            </ReactFlowProvider>
        </div>
    );
}
