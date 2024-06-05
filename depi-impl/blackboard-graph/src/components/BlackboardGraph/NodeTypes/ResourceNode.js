import PropTypes from 'prop-types';
import React, { memo, useEffect, useMemo } from 'react';
import { Handle, Position, useUpdateNodeInternals } from 'reactflow';
import { Box, IconButton } from '@mui/material';
import { ExpandLess as ExpandedLessIcon, ExpandMore as ExpandedMoreIcon } from '@mui/icons-material';
// utils
import { COLORS } from '../../../theme';
import { Resource } from '../../../depiTypes';

ResourceNode.propTypes = {
    id: PropTypes.string,
    selected: PropTypes.bool,
    data: PropTypes.shape({
        label: PropTypes.string,
        onBlackboard: PropTypes.bool,
        inDepi: PropTypes.bool,
        resource: Resource,
        isDirty: PropTypes.bool,
        dependsOnDirty: PropTypes.bool,
        isContainer: PropTypes.bool,
        childrenDepth: PropTypes.number,
        width: PropTypes.number,
        height: PropTypes.number,
        orientation: PropTypes.string, // left, right, top, bottom
        isExpanded: PropTypes.bool,
        setNodeExpanded: PropTypes.func,
    }),
};

function ResourceNode({ id, selected, data }) {
    const {
        width,
        height,
        orientation,
        label,
        onBlackboard,
        inDepi,
        isDirty,
        dependsOnDirty,
        childrenDepth,
        isContainer,
        isExpanded,
        setNodeExpanded,
        resource,
    } = data;

    const updateNodeInternals = useUpdateNodeInternals();
    useEffect(() => {
        updateNodeInternals(id);
    }, [updateNodeInternals, orientation, id]);

    const expandCollapseBtn = useMemo(() => {
        if (!setNodeExpanded || !isContainer) {
            return null;
        }

        if (isExpanded && childrenDepth === 0) {
            return null;
        }

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
    }, [id, isExpanded, childrenDepth, setNodeExpanded, isContainer]);

    const isPureBlackboard = onBlackboard && !inDepi;
    let sanitizedLabel = label;
    // Weird rtl thing - slashes are moved from left to right.
    if (isPureBlackboard && label.length > 1 && label[0] === '/' && !label.endsWith('/')) {
        sanitizedLabel += '/';
        sanitizedLabel = sanitizedLabel.substring(1);
    }

    let color;
    let title = resource.url;

    if (isDirty) {
        color = COLORS.DIRTY;
        title += ' - Resource has changed and is considered dirty.';
    }

    if (dependsOnDirty) {
        color = COLORS.DEPENDS_ON_DIRTY;
        if (isDirty) {
            title += ' It also depends on dirty resources.';
        } else {
            title += ' - Resource depends on dirty resources.';
        }
    }

    return (
        <Box
            sx={{
                fontSize: '10px',
                color,
                boxShadow: selected ? `0 0 3px 3px ${COLORS.SELECTED}` : undefined,
                borderStyle: 'solid',
                borderWidth: '1px',
                borderColor: onBlackboard ? 'black' : '#ccc',
                backgroundColor: onBlackboard ? COLORS.BLACKBOARD_NODE : COLORS.RESOURCE_BG,
                borderRadius: 1,
                width,
                height,
            }}
        >
            <div
                dir={isPureBlackboard ? 'rtl' : undefined}
                style={{
                    marginTop: 4,
                    paddingLeft: 5,
                    paddingRight: 5,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                }}
                title={title}
            >
                {`${isDirty ? '*' : ''}${sanitizedLabel}${isDirty ? '*' : ''}`}
            </div>
            {expandCollapseBtn}
            {orientation === 'left' ? (
                <>
                    <Handle
                        id="source"
                        type="source"
                        isConnectableEnd={false}
                        position={Position.Right}
                        className={'handle-output-port handle-output-port-left'}
                    />
                    <Handle
                        id="target"
                        type="target"
                        position={Position.Right}
                        isConnectableStart={false}
                        className={'handle-input-port handle-input-port-left'}
                    />
                </>
            ) : (
                <>
                    <Handle
                        id="source"
                        type="source"
                        isConnectableEnd={false}
                        position={Position.Left}
                        className={'handle-output-port handle-output-port-right'}
                    />
                    <Handle
                        id="target"
                        type="target"
                        position={Position.Left}
                        isConnectableStart={false}
                        className={'handle-input-port handle-input-port-right'}
                    />
                </>
            )}
        </Box>
    );
}

export default memo(ResourceNode);
