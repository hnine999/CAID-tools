import PropTypes from 'prop-types';
import { useStore } from 'reactflow';
import { memo } from 'react';
import { COLORS } from '../../theme';

ConnectionLine.propTypes = {
    fromX: PropTypes.number,
    fromY: PropTypes.number,
    toX: PropTypes.number,
    toY: PropTypes.number,
    fromHandle: PropTypes.object,
    fromNode: PropTypes.object,
    connectionStatus: PropTypes.string,
};

function ConnectionLine({ fromX, fromY, toX, toY, fromHandle, fromNode, connectionStatus }) {
    const { connectionEndHandle, nodes } = useStore((s) => ({
        connectionEndHandle: s.connectionEndHandle,
        nodes: s.getNodes(),
    }));

    const valid = connectionStatus === 'valid';
    const fromSource = fromHandle.id === 'source';
    const color = valid ? COLORS.BLACKBOARD_EDGE : COLORS.DEPI_EDGE;
    const marker = valid ? 'url(#arrow_head_blackboard)' : 'url(#arrow_head_depi)';
    let label = 'depends on';

    if (valid) {
        const toNode = nodes.find((n) => n.id === connectionEndHandle?.nodeId);
        if (fromSource) {
            label = `${fromNode?.data?.label} depends on ${toNode?.data?.label}`;
        } else {
            label = `${toNode?.data?.label} depends on ${fromNode?.data?.label}`;
        }
    } else if (fromSource) {
        label = `${fromNode?.data?.label} depends on ...`;
    } else {
        label = `... depends on ${fromNode?.data?.label}`;
    }

    return (
        <g>
            <path
                fill="none"
                stroke={color}
                strokeDasharray={valid ? 0 : 5}
                strokeWidth={valid ? 2 : 1}
                d={`M${fromX},${fromY} ${toX},${toY}`}
                markerEnd={fromSource ? marker : undefined}
                markerStart={fromSource ? undefined : marker}
            />
            <text
                fill={color}
                stroke="black"
                strokeWidth={0.5}
                fontSize={valid ? 14 : 12}
                fontWeight="bold"
                textAnchor="middle"
                x={fromX + Math.round((toX - fromX) / 2)}
                y={fromY + Math.round((toY - fromY) / 2) - 4}
            >
                {label}
            </text>
        </g>
    );
}

export default memo(ConnectionLine);
