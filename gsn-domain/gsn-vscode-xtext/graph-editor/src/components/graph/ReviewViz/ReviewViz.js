import PropTypes from 'prop-types';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
// @mui
import { Box, FormControl, RadioGroup, FormControlLabel, Radio, FormLabel } from '@mui/material';
// components
import ReviewTable from './ReviewTable';
// utils
import { DepiMethodsType, NodeType, ResourceStateType } from '../gsnTypes';
import GSN_CONSTANTS from '../GSN_CONSTANTS';

ReviewViz.propTypes = {
    isReadOnly: PropTypes.bool,
    data: PropTypes.arrayOf(NodeType).isRequired,
    model: PropTypes.arrayOf(NodeType).isRequired,
    depiResources: PropTypes.objectOf(ResourceStateType),
    width: PropTypes.number.isRequired,
    height: PropTypes.number.isRequired,
    left: PropTypes.number,
    top: PropTypes.number,
    selectedNode: PropTypes.oneOfType([
        PropTypes.shape({
            nodeId: PropTypes.string,
            treeId: PropTypes.string,
        }),
        PropTypes.arrayOf(PropTypes.string),
    ]),
    setSelectedNode: PropTypes.func.isRequired,
    setSubtreeRoot: PropTypes.func.isRequired,
    setSelectedVisualizer: PropTypes.func.isRequired,
    depiMethods: DepiMethodsType,
};

export default function ReviewViz({
    isReadOnly,
    model,
    width,
    height,
    left,
    top,
    selectedNode,
    setSelectedNode,
    setSubtreeRoot,
    setSelectedVisualizer,
    depiResources,
    data,
    depiMethods,
}) {
    const [nodeType, setNodeType] = useState(GSN_CONSTANTS.TYPES.SOLUTION);
    const [expandedRows, setExpandedRows] = useState([]);

    useEffect(() => {
        if (nodeType === GSN_CONSTANTS.TYPES.SOLUTION) {
            setExpandedRows((prevState) => (prevState.length > 0 ? [] : prevState));
        }
    }, [nodeType]);

    const nodesData = useMemo(() => {
        function getState({ uuid }) {
            if (!depiResources) {
                return GSN_CONSTANTS.NODE_DEPI_STATES.LOADING;
            }

            return depiResources[uuid] ? depiResources[uuid].status : GSN_CONSTANTS.NODE_DEPI_STATES.NO_DEPI_RESOURCE;
        }

        const nodeNotRevieved = ({ status }) => !status || status === GSN_CONSTANTS.NODE_STATUS_OPTIONS.NOT_REVIEWED;

        const nodesData = data
            .filter((node) => node.type === nodeType)
            .map((node) => ({
                id: node.id,
                node,
                hasDirt: false,
                hasNotReviewed: false,
                reviewed: false,
                solutions: [],
                state: nodeType === GSN_CONSTANTS.TYPES.SOLUTION ? getState(node) : null,
            }))
            .sort((a, b) => a.node.name.localeCompare(b.node.name));

        if (nodeType === GSN_CONSTANTS.TYPES.GOAL) {
            const nodeMap = {};
            const idToStat = {};
            const idToNodeInfo = {};

            model.forEach((n) => {
                nodeMap[n.id] = n;
            });

            const checkDirtRec = (node, nodeInfo) => {
                if (node.type === GSN_CONSTANTS.TYPES.SOLUTION) {
                    if (getState(node) === GSN_CONSTANTS.NODE_DEPI_STATES.RESOURCE_DIRTY) {
                        idToStat[node.id] = {
                            dirty: true,
                            notReviewed: false,
                        };
                    } else {
                        idToStat[node.id] = {
                            dirty: false,
                            notReviewed: false,
                        };
                    }

                    return idToStat[node.id];
                }

                if (Object.hasOwn(idToStat, node.id)) {
                    if (nodeInfo) {
                        nodeInfo.hasDirt = idToStat[node.id].dirty;
                        nodeInfo.hasNotReviewed = idToStat[node.id].notReviewed;
                    }

                    return idToStat[node.id];
                }

                const stats = {
                    dirty: false,
                    notReviewed: false,
                };
                (node[GSN_CONSTANTS.RELATION_TYPES.SOLVED_BY] || []).forEach((childId) => {
                    const childStats = checkDirtRec(nodeMap[childId]);
                    stats.dirty = stats.dirty || childStats.dirty;
                    stats.notReviewed = stats.notReviewed || childStats.notReviewed;
                });

                idToStat[node.id] = stats;
                if (nodeInfo) {
                    nodeInfo.hasDirt = stats.dirty;
                    nodeInfo.hasNotReviewed = stats.notReviewed;
                }

                return stats;
            };

            nodesData.forEach((nodeInfo) => {
                idToNodeInfo[nodeInfo.id] = nodeInfo;
                checkDirtRec(nodeInfo.node, nodeInfo);
                nodeInfo.reviewed = !nodeNotRevieved(nodeInfo.node);
            });

            expandedRows.forEach((nodeId) => {
                const solutions = new Map();
                const traverseRec = (id) => {
                    const node = nodeMap[id];
                    if (node.type === GSN_CONSTANTS.TYPES.SOLUTION && !solutions.has(id)) {
                        solutions.set(id, {
                            id,
                            node,
                            state: getState(node),
                        });
                    }

                    (node[GSN_CONSTANTS.RELATION_TYPES.SOLVED_BY] || []).forEach(traverseRec);
                };

                traverseRec(nodeId);

                idToNodeInfo[nodeId].solutions = [...solutions.values()];
            });
        }

        return nodesData;
    }, [data, depiResources, nodeType, model, expandedRows]);

    const onExpandCollapseRow = useCallback((nodeId) => {
        setExpandedRows((prevState) =>
            prevState.includes(nodeId) ? prevState.filter((id) => id !== nodeId) : [...prevState, nodeId]
        );
    }, []);

    return (
        <Box
            style={{
                position: 'absolute',
                top,
                left,
                width,
                height,
            }}
        >
            <FormControl
                style={{
                    position: 'absolute',
                    top: 0,
                    right: 0,
                }}
            >
                <FormLabel style={{ fontSize: 12 }} id="radio-buttons-group-type-label">
                    Node Type
                </FormLabel>
                <RadioGroup row value={nodeType} onChange={(e) => setNodeType(e.target.value)}>
                    <FormControlLabel
                        value={GSN_CONSTANTS.TYPES.GOAL}
                        control={<Radio size="small" />}
                        label={GSN_CONSTANTS.TYPES.GOAL}
                    />
                    <FormControlLabel
                        value={GSN_CONSTANTS.TYPES.SOLUTION}
                        control={<Radio size="small" />}
                        label={GSN_CONSTANTS.TYPES.SOLUTION}
                    />
                </RadioGroup>
            </FormControl>
            <ReviewTable
                isReadOnly={isReadOnly}
                height={height}
                showState={nodeType === GSN_CONSTANTS.TYPES.SOLUTION}
                showStatus
                showReview={false}
                showSummary
                showUuid={false}
                data={nodesData}
                expandedRows={expandedRows}
                selectedNode={selectedNode}
                setSelectedNode={setSelectedNode}
                setSubtreeRoot={setSubtreeRoot}
                setSelectedVisualizer={setSelectedVisualizer}
                onExpandCollapseRow={nodeType === GSN_CONSTANTS.TYPES.GOAL ? onExpandCollapseRow : undefined}
                depiMethods={depiMethods}
            />
        </Box>
    );
}
