import PropTypes from 'prop-types';
import React, { memo, useMemo, useCallback, useEffect } from 'react';
import { useUpdateNodeInternals } from 'reactflow';
// @mui
import { Box, IconButton } from '@mui/material';
import {
    OpenWith as OpenWithIcon,
    SwitchLeft as SwitchLeftIcon,
    SwitchRight as SwitchRightIcon,
    ExpandLess as ExpandedLessIcon,
    ExpandMore as ExpandedMoreIcon,
} from '@mui/icons-material';
// utils
import useAggregateHandles from './useAggregateHandles';
import { COLORS } from '../../../theme';
import { ResourceGroup } from '../../../depiTypes';
import { getShortDisplayVersion } from '../../../utils';

ResourceGroupNode.propTypes = {
    id: PropTypes.string,
    selected: PropTypes.bool,
    data: PropTypes.shape({
        resourceGroup: ResourceGroup,
        width: PropTypes.number,
        height: PropTypes.number,
        orientation: PropTypes.string, // 'left', 'right'
        onSwitchOrientation: PropTypes.func,
        isExpanded: PropTypes.bool,
        setNodeExpanded: PropTypes.func,
        childrenDepth: PropTypes.number,
    }),
};

function ResourceGroupNode({ id, selected, data }) {
    const {
        width,
        height,
        resourceGroup,
        orientation,
        onSwitchOrientation,
        isExpanded,
        setNodeExpanded,
        childrenDepth,
    } = data;

    const updateNodeInternals = useUpdateNodeInternals();
    useEffect(() => {
        updateNodeInternals(id);
    }, [updateNodeInternals, orientation, id]);

    const onSwitchClick = useCallback(() => {
        if (orientation === 'left') {
            onSwitchOrientation(id, 'right');
            return;
        }

        onSwitchOrientation(id, 'left');
    }, [orientation, onSwitchOrientation, id]);

    const expandCollapseBtn = useMemo(() => {
        if (!setNodeExpanded || (childrenDepth === 0 && isExpanded)) {
            return null;
        }

        const onExpandCollapse = (e) => {
            setNodeExpanded(id, !isExpanded, e.ctrlKey);
            e.stopPropagation();
        };

        return isExpanded ? (
            <IconButton onClick={onExpandCollapse} title="Collapse">
                <ExpandedLessIcon sx={{ fontSize: 12 }} />
            </IconButton>
        ) : (
            <IconButton onClick={onExpandCollapse} title="Expand">
                <ExpandedMoreIcon sx={{ fontSize: 12 }} />
            </IconButton>
        );
    }, [id, isExpanded, setNodeExpanded, childrenDepth]);

    const handles = useAggregateHandles(isExpanded, orientation);

    const version = getShortDisplayVersion(resourceGroup.version);

    return (
        <Box
            sx={{
                backgroundColor: resourceGroup.isActiveInEditor
                    ? COLORS.RESOURCE_GROUP_ACTIVE_IN_EDITOR
                    : COLORS.RESOURCE_GROUP_BG,
                border: '2px solid black',
                boxShadow: selected ? `0 0 4px 4px ${COLORS.SELECTED}` : undefined,
                borderRadius: 1,
                '&:hover': {
                    cursor: 'move',
                },
                minWidth: 180,
                width,
                height,
            }}
            className="depi-drag-handle"
        >
            <Box sx={{ position: 'absolute', top: 15, right: 0 }}>
                <IconButton onClick={onSwitchClick} title="Switch port orientation">
                    {orientation === 'left' ? (
                        <SwitchRightIcon sx={{ fontSize: 12 }} />
                    ) : (
                        <SwitchLeftIcon sx={{ fontSize: 12 }} />
                    )}
                </IconButton>
                <IconButton title="Drag to Move" className="depi-drag-handle">
                    <OpenWithIcon sx={{ fontSize: 12 }} />
                </IconButton>
                {expandCollapseBtn}
            </Box>
            <div style={{ fontSize: 12, fontWeight: 'bold', paddingTop: 2, paddingLeft: 5 }} title={id}>
                {resourceGroup.name}
            </div>
            <div style={{ fontSize: 8, paddingLeft: 5, color: COLORS.GREY_TEXT }}>
                {`${resourceGroup.toolId}: ${version}`}
            </div>
            {handles}
        </Box>
    );
}

export default memo(ResourceGroupNode);
