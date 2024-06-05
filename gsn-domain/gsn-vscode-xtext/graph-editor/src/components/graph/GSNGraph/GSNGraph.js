import PropTypes from 'prop-types';
import { useState, useEffect } from 'react';
import { ReactFlowProvider } from 'reactflow';
// components
import FlowGraph from './FlowGraph';
import OverviewGraph from './OverviewGraph';
import ReviewViz from '../ReviewViz';
// utils
import { DepiMethodsType, NodeType, ResourceStateType } from '../gsnTypes';

GSNGraph.propTypes = {
    selectedVisualizer: PropTypes.string,
    data: PropTypes.arrayOf(NodeType).isRequired,
    model: PropTypes.arrayOf(NodeType).isRequired,
    depiResources: PropTypes.objectOf(ResourceStateType),
    filter: PropTypes.shape({
        expandAll: PropTypes.bool,
        highlighted: PropTypes.object,
    }),
    reviewTag: PropTypes.string,
    width: PropTypes.number.isRequired,
    height: PropTypes.number.isRequired,
    left: PropTypes.number,
    top: PropTypes.number,
    nonReactive: PropTypes.bool,
    minZoom: PropTypes.number,
    selectedNode: PropTypes.oneOfType([
        PropTypes.shape({
            nodeId: PropTypes.string,
            treeId: PropTypes.string,
        }),
        PropTypes.arrayOf(PropTypes.string),
    ]),
    setSelectedNode: PropTypes.func,
    setSubtreeRoot: PropTypes.func.isRequired,
    setSelectedVisualizer: PropTypes.func.isRequired,
    onConnectNodes: PropTypes.func,
    showReferencesAtStart: PropTypes.bool,
    depiMethods: DepiMethodsType,
};

export default function GSNGraph({ selectedVisualizer = 'default', data, ...rest }) {
    // TODO: Generalize this at some point..
    const [cachedVisualizers, setCachedVisualizers] = useState({
        default: true,
        table: false,
        overview: false,
        overview2: false,
    });

    useEffect(() => {
        setCachedVisualizers((prevCache) => {
            if (!prevCache[selectedVisualizer]) {
                return { ...prevCache, [selectedVisualizer]: true };
            }

            return prevCache;
        });
    }, [selectedVisualizer]);

    return (
        <>
            {cachedVisualizers.overview ? (
                <div style={{ display: selectedVisualizer === 'overview' ? undefined : 'none' }}>
                    <OverviewGraph data={data} {...rest} />
                </div>
            ) : null}
            {cachedVisualizers.overview2 ? (
                <div style={{ display: selectedVisualizer === 'overview2' ? undefined : 'none' }}>
                    <OverviewGraph layout={layout2} data={data} {...rest} />
                </div>
            ) : null}
            {cachedVisualizers.table ? (
                <div style={{ display: selectedVisualizer === 'table' ? undefined : 'none' }}>
                    <ReviewViz data={data} {...rest} />
                </div>
            ) : null}

            <div style={{ display: selectedVisualizer === 'default' ? undefined : 'none' }}>
                <ReactFlowProvider>
                    <FlowGraph data={data} {...rest} />
                </ReactFlowProvider>
            </div>
        </>
    );
}

const layout2 = {
    name: 'cise',
    animate: true,
    allowNodesInsideCircle: false,
    // maxRatioOfNodesInsideCircle: 0.25,
    nodeSeparation: 5,
    clusters: (node) => node.data('clusterId'),
    idealInterClusterEdgeLengthCoefficient: 2,
};
