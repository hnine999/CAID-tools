import PropTypes from 'prop-types';
import { memo } from 'react';
import { getBezierPath, BaseEdge } from 'reactflow';
// utils
import { COLORS } from '../../theme';
import { ResourceLink } from '../../depiTypes';

LinkEdge.propTypes = {
    id: PropTypes.string,
    selected: PropTypes.bool,
    data: PropTypes.shape({
        onBlackboard: PropTypes.bool,
        link: ResourceLink,
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

function LinkEdge({ id, selected, data, ...pathProps }) {
    // console.log(id);
    const [path] = getBezierPath({
        ...pathProps,
    });

    const { onBlackboard, link, showDirtyness } = data;
    const style = {
        strokeWidth: onBlackboard ? 2 : 1,
        strokeOpacity: 1,
        stroke: onBlackboard ? COLORS.BLACKBOARD_EDGE : COLORS.DEPI_EDGE,
    };

    let markerEnd = onBlackboard ? 'url(#arrow_head_blackboard' : 'url(#arrow_head_depi';

    if (link.dirty || link.inferredDirtiness.length > 0) {
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

export default memo(LinkEdge);
