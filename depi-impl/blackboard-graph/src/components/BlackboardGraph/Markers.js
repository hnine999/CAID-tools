import PropTypes from 'prop-types';
import { COLORS } from '../../theme';

Marker.propTypes = {
    id: PropTypes.string.isRequired,
    stroke: PropTypes.string.isRequired,
    fill: PropTypes.string.isRequired,
};

function Marker({ id, stroke, fill }) {
    return (
        <marker
            id={id}
            className="react-flow__arrowhead"
            markerWidth="12.5"
            markerHeight="12.5"
            viewBox="-10 -10 20 20"
            markerUnits="strokeWidth"
            orient="auto-start-reverse"
            refX="0"
            refY="0"
        >
            <polyline
                stroke={stroke}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1"
                fill={fill}
                points="-5,-4 0,0 -5,4 -5,-4"
            />
        </marker>
    );
}

export default function Markers() {
    return (
        <svg style={{ position: 'absolute', top: 0, left: 0, width: 0, height: 0 }}>
            <defs>
                <Marker id="arrow_head_depi" stroke={COLORS.DEPI_EDGE} fill={COLORS.DEPI_EDGE} />
                <Marker id="arrow_head_depi_dirty" stroke={COLORS.DIRTY} fill={COLORS.DIRTY} />
                <Marker id="arrow_head_depi_dirty_selected" stroke={COLORS.SELECTED} fill={COLORS.DIRTY} />
                <Marker id="arrow_head_depi_selected" stroke={COLORS.SELECTED} fill={COLORS.DEPI_EDGE} />
                <Marker id="arrow_head_blackboard" stroke={COLORS.BLACKBOARD_EDGE} fill={COLORS.BLACKBOARD_EDGE} />
                <Marker id="arrow_head_blackboard_selected" stroke={COLORS.SELECTED} fill={COLORS.BLACKBOARD_EDGE} />
            </defs>
        </svg>
    );
}
