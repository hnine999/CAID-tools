import PropTypes from 'prop-types';
import { useMemo, useCallback } from 'react';
// @mui
import { Button, Grid, Typography } from '@mui/material';

// components
import { StringInput } from '../FormComponents';
import WrapWithLabel from './WrapWithLabel';
// utils
import { NodeType } from '../gsnTypes';
import { labelStyle } from '../FormComponents/common';
import GSN_CONSTANTS from '../GSN_CONSTANTS';
// ----------------------------------------------------------------------
const buttonStyle = { fontSize: '0.8rem', textTransform: 'none', fontWeight: '600' };

ArtifactsEditor.propTypes = {
    nodeData: NodeType,
    isReadOnly: PropTypes.bool,
    onAttributeChange: PropTypes.func,
};

export default function ArtifactsEditor({ nodeData, isReadOnly, onAttributeChange }) {
    const resetStatusAfterArtifactChange = useCallback(() => {
        if (!isReadOnly && nodeData.status && nodeData.status !== GSN_CONSTANTS.NODE_STATUS_OPTIONS.NOT_REVIEWED) {
            onAttributeChange(nodeData.id, 'status', GSN_CONSTANTS.NODE_STATUS_OPTIONS.NOT_REVIEWED);
        }
    }, [isReadOnly, onAttributeChange, nodeData]);

    const artifactsItems = useMemo(() => {
        const { artifacts } = nodeData;
        if (!artifacts || artifacts.length === 0) {
            return [
                <WrapWithLabel key={'no-artifacts'} label={'Artifacts'}>
                    <Typography style={{ color: 'grey', fontStyle: 'italic', ...labelStyle }} variant="body2">
                        None added ..
                    </Typography>
                </WrapWithLabel>,
            ];
        }

        return artifacts.map((artifactStr, idx) => (
            <WrapWithLabel key={`${idx}`} label={'Artifact'}>
                <StringInput
                    isReadOnly={isReadOnly}
                    initText={artifactStr}
                    checkFunction={(newValue) => {
                        // TODO: What is the regex here?
                        if (newValue.includes(';')) {
                            return { valid: false, hint: 'Cannot contain ";"' };
                        }

                        return { valid: true, hint: '' };
                    }}
                    onSubmit={(newValue) => {
                        const newArtifacts = [...artifacts];
                        newArtifacts[idx] = newValue;
                        onAttributeChange(nodeData.id, 'artifacts', newArtifacts);
                        resetStatusAfterArtifactChange();
                    }}
                    onClear={() => {
                        const newArtifacts = artifacts.filter((_, i) => i !== idx);
                        onAttributeChange(nodeData.id, 'artifacts', newArtifacts);
                        resetStatusAfterArtifactChange();
                    }}
                />
            </WrapWithLabel>
        ));
    }, [nodeData, isReadOnly, onAttributeChange, resetStatusAfterArtifactChange]);

    return (
        <Grid container spacing={1} style={{ padding: 10 }}>
            {artifactsItems}
            <WrapWithLabel label={''}>
                <Button
                    sx={buttonStyle}
                    title="Add an Artifact"
                    onClick={() => {
                        const newArtifacts = [...(nodeData.artifacts || [])];
                        newArtifacts.push('');
                        onAttributeChange(nodeData.id, 'artifacts', newArtifacts);
                    }}
                >
                    + Artifact
                </Button>
            </WrapWithLabel>
        </Grid>
    );
}
