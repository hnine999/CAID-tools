import PropTypes from 'prop-types';
import React, { memo, useMemo, useEffect } from 'react';
import { useUpdateNodeInternals } from 'reactflow';
// @mui
import { Box, IconButton } from '@mui/material';
import { ExpandLess as ExpandedLessIcon, ExpandMore as ExpandedMoreIcon } from '@mui/icons-material';

// utils
import { COLORS } from '../../../theme';
import useAggregateHandles from './useAggregateHandles';

ContainerNode.propTypes = {
    id: PropTypes.string,
    data: PropTypes.shape({
        label: PropTypes.string,
        resourceGroupId: PropTypes.string,
        width: PropTypes.number,
        height: PropTypes.number,
        orientation: PropTypes.string,
        isExpanded: PropTypes.bool,
        setNodeExpanded: PropTypes.func.isRequired,
    }),
};

function ContainerNode({ id, data }) {
    const { width, height, orientation, isExpanded, setNodeExpanded } = data;

    const updateNodeInternals = useUpdateNodeInternals();
    useEffect(() => {
        updateNodeInternals(id);
    }, [updateNodeInternals, orientation, id]);

    const expandCollapseBtn = useMemo(() => {
        const onExpandCollapse = (e) => {
            setNodeExpanded(id, !isExpanded, e.ctrlKey);
            e.stopPropagation();
        };

        return (
            <Box sx={{ position: 'absolute', top: 0, right: 0 }}>
                {isExpanded ? (
                    <IconButton onClick={onExpandCollapse} title="Collapse">
                        <ExpandedLessIcon sx={{ fontSize: 12 }} />
                    </IconButton>
                ) : (
                    <IconButton onClick={onExpandCollapse} title="Expand">
                        <ExpandedMoreIcon sx={{ fontSize: 12 }} />
                    </IconButton>
                )}
            </Box>
        );
    }, [id, isExpanded, setNodeExpanded]);

    const handles = useAggregateHandles(isExpanded, orientation);

    return (
        <Box
            sx={{
                backgroundColor: COLORS.CONTAINER_BG,
                fontSize: '10px',
                border: '1px dashed #ccc',
                borderRadius: 1,
                width,
                height,
            }}
        >
            <div style={{ paddingLeft: 5, marginTop: 4, color: COLORS.GREY_TEXT }} title={id}>
                {data.label}
            </div>
            {expandCollapseBtn}
            {handles}
        </Box>
    );
}

export default memo(ContainerNode);
