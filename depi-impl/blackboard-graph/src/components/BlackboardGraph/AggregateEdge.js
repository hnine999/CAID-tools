import PropTypes from 'prop-types';
import { memo } from 'react';
import { getBezierPath, BaseEdge } from 'reactflow';
// utils
import { COLORS } from '../../theme';
import { ResourceLink } from '../../depiTypes';

AggregateEdge.propTypes = {
    id: PropTypes.string,
    selected: PropTypes.bool,
    data: PropTypes.shape({
        links: PropTypes.arrayOf(ResourceLink),
        showDirtyness: PropTypes.bool,
    }),
    // Path props
    sourceX: PropTypes.number,
    sourceY: PropTypes.number,
    targetX: PropTypes.number,
    targetY: PropTypes.number,
    sourcePosition: PropTypes.string,
    targetPosition: PropTypes.string,
};

function AggregateEdge({ id, selected, data, ...pathProps }) {
    // console.log(id);
    const [path] = getBezierPath({
        ...pathProps,
    });

    const { links, showDirtyness } = data;
    const style = {
        strokeWidth: links.length > 5 ? 5 : links.length, // TODO: We need to tweak this number
        strokeOpacity: 1,
        stroke: COLORS.DEPI_EDGE,
    };

    let markerEnd = 'url(#arrow_head_depi';

    if (links.some((link) => link.dirty || link.inferredDirtiness.length > 0)) {
        style.stroke = COLORS.DIRTY;
        markerEnd += '_dirty';
        if (showDirtyness) {
            style.strokeDasharray = 5;
            style.animation = '1s linear 0s infinite normal none running dashdraw';
            style.animationDirection = 'reverse';
        }
    }

    if (selected) {
        markerEnd += '_selected';
        style.stroke = COLORS.SELECTED;
    }

    markerEnd += ')';

    return <BaseEdge id={id} style={style} path={path} markerEnd={markerEnd} />;
}

export default memo(AggregateEdge);
