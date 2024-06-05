import PropTypes from 'prop-types';
import { memo } from 'react';
import { getBezierPath, BaseEdge } from 'reactflow';
// utils
import { COLORS } from '../../theme';
import { ResourceLink } from '../../depiTypes';

DependencyLinkEdge.propTypes = {
    id: PropTypes.string,
    selected: PropTypes.bool,
    data: PropTypes.shape({
        isReadOnly: PropTypes.bool,
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

function DependencyLinkEdge({ id, selected, data, ...pathProps }) {
    // console.log(id);
    const [path] = getBezierPath({
        ...pathProps,
    });

    const { link, showDirtyness } = data;
    const { dirty, inferredDirtiness } = link;
    const isDirty = dirty || inferredDirtiness.length > 0;

    const style = {
        strokeWidth: 2,
        strokeOpacity: 1,
        stroke: COLORS.DEPI_EDGE,
    };

    let markerEnd = 'url(#arrow_head_depi';

    if (isDirty) {
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
        style.strokeWidth = 3;
    }

    markerEnd += ')';

    return <BaseEdge id={id} style={style} path={path} markerEnd={markerEnd} />;
}

export default memo(DependencyLinkEdge);
