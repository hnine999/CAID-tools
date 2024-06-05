import PropTypes from 'prop-types';
import { useCallback } from 'react';
// @mui
import { IconButton, Grid } from '@mui/material';
import { PlayForWork as PlayForWorkIcon } from '@mui/icons-material';
// components
import { MultiSelectInput } from '../FormComponents';
import WrapWithLabel from './WrapWithLabel';
// utils
import GSN_CONSTANTS from '../GSN_CONSTANTS';
import { NodeType } from '../gsnTypes';
import modelUtils from '../modelUtils';

// ----------------------------------------------------------------------

const { NODE_STATUS_OPTIONS } = GSN_CONSTANTS;

NodeStatusInfo.propTypes = {
    nodeData: NodeType,
    model: PropTypes.arrayOf(NodeType).isRequired,
    isReadOnly: PropTypes.bool,
    onAttributeChange: PropTypes.func,
};

export default function NodeStatusInfo({ nodeData, model, isReadOnly, onAttributeChange }) {
    const statusOptions = Object.keys(NODE_STATUS_OPTIONS).map((key) => ({
        value: NODE_STATUS_OPTIONS[key],
        label: NODE_STATUS_OPTIONS[key],
    }));
    const statusValue = nodeData.status || statusOptions[0].value;

    const onNewValue = useCallback(
        (newValue, propagate) => {
            let childIds = [];
            if (propagate) {
                childIds = Object.keys(modelUtils.getChildIds(model, nodeData.id).children);
            }

            onAttributeChange(nodeData.id, 'status', newValue, childIds);
        },
        [nodeData, model, onAttributeChange]
    );

    return (
        <Grid container spacing={1} style={{ padding: 10 }}>
            <WrapWithLabel label={'Status'}>
                <MultiSelectInput
                    isReadOnly={isReadOnly}
                    value={statusValue}
                    options={statusOptions}
                    onSubmit={onNewValue}
                />
                <IconButton
                    sx={{ marginLeft: 1 }}
                    title={`Propagate status "${statusValue}" to all children`}
                    variant="outlined"
                    onClick={() => onNewValue(statusValue, true)}
                >
                    <PlayForWorkIcon />
                </IconButton>
            </WrapWithLabel>
        </Grid>
    );
}
