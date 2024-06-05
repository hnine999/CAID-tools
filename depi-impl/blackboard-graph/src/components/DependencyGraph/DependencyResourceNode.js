import React, { memo } from 'react';
import PropTypes from 'prop-types';
import { Handle, Position, useStore } from 'reactflow';
// utils
import { COLORS } from '../../theme';
import { Resource } from '../../depiTypes';
import { getShortDisplayVersion } from '../../utils';

const zoomSelector = (s) => s.transform[2];

DependencyResourceNode.propTypes = {
    id: PropTypes.string,
    selected: PropTypes.bool,
    data: PropTypes.shape({
        isStartResource: PropTypes.bool,
        resource: Resource,
        isReadOnly: PropTypes.bool,
        width: PropTypes.number,
        height: PropTypes.number,
    }),
};

function DependencyResourceNode({ id, selected, data }) {
    const zoom = useStore(zoomSelector);
    const { resource, isStartResource, isReadOnly, width, height } = data;
    const { name, resourceGroupUrl, resourceGroupName, resourceGroupVersion, toolId } = resource;

    if (id && zoom && isReadOnly) {
        // Do something
    }

    return (
        <div
            style={{
                borderColor: isStartResource ? 'black' : 'grey',
                backgroundColor: selected ? COLORS.SELECTED : undefined,
                textAlign: 'center',
                borderStyle: 'solid',
                borderRadius: '25%',
                width,
                height,
            }}
        >
            <div style={{ marginTop: 12, fontSize: 14, fontWeight: 'bold', wordWrap: 'break-word' }}>{name}</div>
            <div style={{ marginTop: 10, fontSize: 12, wordWrap: 'break-word' }} title={resourceGroupUrl}>
                {resourceGroupName}
            </div>
            <div style={{ marginTop: 6, fontSize: 10, color: COLORS.GREY_TEXT }}>
                {`${toolId}: ${getShortDisplayVersion(resourceGroupVersion)}`}
            </div>

            <Handle type="target" position={Position.Left} style={{ opacity: 0, left: 0 }} />
            <Handle type="source" position={Position.Right} style={{ opacity: 0, right: 0 }} />

            <Handle type="target" id="targetCircular" position={Position.Bottom} style={{ opacity: 0, bottom: 0 }} />
            <Handle type="target" id="targetCircular" position={Position.Top} style={{ opacity: 0, top: 0 }} />
        </div>
    );
}

export default memo(DependencyResourceNode);
