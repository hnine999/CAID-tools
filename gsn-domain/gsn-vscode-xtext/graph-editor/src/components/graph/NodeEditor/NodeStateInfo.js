import PropTypes from 'prop-types';
import { useMemo, useCallback } from 'react';
// @mui
import { IconButton, Grid, Typography } from '@mui/material';
import {
    LinkOff as LinkOffIcon,
    AddLink as AddLinkIcon,
    Insights as InsightsIcon,
    HourglassTop as HourglassTopIcon,
    RemoveCircleOutline as RemoveCircleOutlineIcon,
} from '@mui/icons-material';
// components
import { HyperLink } from '../FormComponents';
import WrapWithLabel from './WrapWithLabel';
// utils
import GSN_CONSTANTS from '../GSN_CONSTANTS';
import { NodeType, DepiMethodsType, ResourceStateType } from '../gsnTypes';
import { labelStyle } from '../FormComponents/common';

// ----------------------------------------------------------------------
// Note that this component doesn't even exist if depiMethods are not provided, that is if depi is deactivated.
// This means we do not have to handle the case of depi being deactivated here.

const { NODE_DEPI_STATES, NODE_STATUS_OPTIONS } = GSN_CONSTANTS;

NodeStateInfo.propTypes = {
    nodeData: NodeType,
    depiResources: PropTypes.objectOf(ResourceStateType),
    isReadOnly: PropTypes.bool,
    onAttributeChange: PropTypes.func,
    depiMethods: DepiMethodsType,
};

export default function NodeStateInfo({ nodeData, isReadOnly, onAttributeChange, depiMethods, depiResources }) {
    const { depiState, evidence } = useMemo(() => {
        if (!depiResources) {
            return { depiState: NODE_DEPI_STATES.LOADING, evidence: [] };
        }

        const depiResource = depiResources[nodeData.uuid];

        if (!depiResource) {
            return { depiState: NODE_DEPI_STATES.NO_DEPI_RESOURCE, evidence: [] };
        }

        return { depiState: depiResource.status, evidence: depiResource.evidence };
    }, [nodeData.uuid, depiResources]);

    const resetStatusAfterEvidenceChange = useCallback(() => {
        if (!isReadOnly && nodeData.status && nodeData.status !== NODE_STATUS_OPTIONS.NOT_REVIEWED) {
            onAttributeChange(nodeData.id, 'status', NODE_STATUS_OPTIONS.NOT_REVIEWED);
        }
    }, [isReadOnly, onAttributeChange, nodeData]);

    const actions = useMemo(() => {
        if (!depiMethods) {
            return [];
        }

        const actions = [];

        switch (depiState) {
            case NODE_DEPI_STATES.NO_DEPI_RESOURCE:
                actions.push(
                    <IconButton
                        disabled={isReadOnly}
                        key={'addAsResource'}
                        title={'Add as Resource'}
                        onClick={() => {
                            depiMethods
                                .addAsResource({ nodeId: nodeData.id, uuid: nodeData.uuid })
                                .then(resetStatusAfterEvidenceChange);
                        }}
                    >
                        <AddLinkIcon />
                    </IconButton>
                );
                break;
            case NODE_DEPI_STATES.NO_LINKED_EVIDENCE:
            case NODE_DEPI_STATES.RESOURCE_UP_TO_DATE:
            case NODE_DEPI_STATES.RESOURCE_DIRTY:
                actions.push(
                    <IconButton
                        key={'showDependencyGraph'}
                        title={'Show Dependency Graph'}
                        onClick={() => {
                            depiMethods.showDependencyGraph({ nodeId: nodeData.id, uuid: nodeData.uuid });
                        }}
                    >
                        <InsightsIcon />
                    </IconButton>,
                    <IconButton
                        disabled={isReadOnly}
                        key={'removeAsResource'}
                        title={'Remove as Resource'}
                        onClick={() => {
                            depiMethods
                                .removeAsResource({ nodeId: nodeData.id, uuid: nodeData.uuid })
                                .then(resetStatusAfterEvidenceChange);
                        }}
                    >
                        <LinkOffIcon />
                    </IconButton>,
                    <IconButton
                        disabled={isReadOnly}
                        key={'linkEvidence'}
                        title={'Link to Evidence'}
                        onClick={() => {
                            depiMethods
                                .linkEvidence({ nodeId: nodeData.id, uuid: nodeData.uuid })
                                .then(resetStatusAfterEvidenceChange);
                        }}
                    >
                        <AddLinkIcon />
                    </IconButton>
                );
                break;
            case NODE_DEPI_STATES.LOADING:
                actions[1] = (
                    <IconButton key={'Loading..'} disabled title={'Fetching data ...'}>
                        <HourglassTopIcon />
                    </IconButton>
                );
                break;
            default:
                return [];
        }

        return actions;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [depiMethods, nodeData.id, nodeData.uuid, depiState]);

    return (
        <Grid container spacing={1} style={{ padding: 10 }}>
            {depiMethods ? (
                <>
                    <WrapWithLabel label={'State'}>
                        <Typography style={{ ...labelStyle, color: 'grey' }} variant="body1">
                            {depiState}
                        </Typography>
                        {actions}
                    </WrapWithLabel>
                    {evidence.length > 0 ? (
                        <WrapWithLabel label={'Evidence'}>
                            {evidence.map((resource) => (
                                <Grid container key={`${resource.toolId}#${resource.resourceGroupUrl}#${resource.url}`}>
                                    <Grid item xs>
                                        <Typography
                                            title={resource.resourceGroupUrl}
                                            sx={{ marginTop: '9px', color: 'rgba(0, 0, 0, 0.54)' }}
                                            variant="body1"
                                        >
                                            {resource.toolId}: {resource.resourceGroupUrl.split('/').pop()}
                                        </Typography>
                                    </Grid>
                                    <Grid item xs={false}>
                                        <IconButton
                                            size="sm"
                                            title="Unlink evidence"
                                            disabled={isReadOnly}
                                            onClick={() => {
                                                depiMethods
                                                    .unlinkEvidence(
                                                        { nodeId: nodeData.id, uuid: nodeData.uuid },
                                                        resource
                                                    )
                                                    .then(resetStatusAfterEvidenceChange);
                                            }}
                                        >
                                            <RemoveCircleOutlineIcon style={{ width: 14, height: 14 }} />
                                        </IconButton>
                                    </Grid>
                                    <Grid item xs={12}>
                                        <HyperLink
                                            title="Reveal Evidence"
                                            value={resource.name}
                                            onClick={() => {
                                                depiMethods.revealEvidence(resource);
                                            }}
                                            sx={{ marginTop: 0 }}
                                        />
                                        <Typography
                                            title={`version: ${resource.resourceGroupVersion}`}
                                            sx={{ fontSize: '10px', color: 'grey' }}
                                            variant="body2"
                                        >
                                            {resource.url}
                                        </Typography>
                                    </Grid>
                                </Grid>
                            ))}
                        </WrapWithLabel>
                    ) : null}
                </>
            ) : null}
        </Grid>
    );
}
