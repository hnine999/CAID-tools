import React from 'react';
import PropTypes from 'prop-types';
// @mui
import { IconButton, Grid, Typography } from '@mui/material';
import {
    AutoFixNormal as AutoFixNormalIcon,
    AutoFixHigh as AutoFixHighIcon,
    OpenInNew as OpenInNewIcon,
    Difference as DifferenceIcon,
} from '@mui/icons-material';
// utils
import { ResourceLink } from '../../depiTypes';
import { getFullResourceId } from '../../utils';

// ----------------------------------------------------------------------
DirtinessSection.propTypes = {
    isReadOnly: PropTypes.bool,
    link: ResourceLink,
    onRevealInEditor: PropTypes.func.isRequired,
    onViewResourceDiff: PropTypes.func.isRequired,
    onMarkLinksClean: PropTypes.func.isRequired,
    onMarkInferredDirtinessClean: PropTypes.func.isRequired,
};

export default function DirtinessSection({
    isReadOnly,
    link,
    onRevealInEditor,
    onViewResourceDiff,
    onMarkLinksClean,
    onMarkInferredDirtinessClean,
}) {
    const getResourceElm = ({ resource, lastCleanVersion, isDirectDirtiness }) => {
        const getMarkAsCleanFn = (propagate) => {
            if (isDirectDirtiness) {
                return () => {
                    onMarkLinksClean([link], propagate);
                };
            }
            return () => {
                onMarkInferredDirtinessClean(link, resource, propagate);
            };
        };

        return (
            <React.Fragment key={getFullResourceId(resource)}>
                <Grid item xs={1} />
                <Grid item xs={6}>
                    <Typography variant="body2">{resource.name}</Typography>
                </Grid>
                <Grid item xs={5}>
                    <IconButton
                        size="small"
                        title="Reveal resource in editor"
                        onClick={() => onRevealInEditor(resource)}
                    >
                        <OpenInNewIcon sx={{ fontSize: 18 }} />
                    </IconButton>
                    <IconButton
                        size="small"
                        title="View changes since last clean"
                        onClick={() => onViewResourceDiff(resource, lastCleanVersion)}
                    >
                        <DifferenceIcon sx={{ fontSize: 18 }} />
                    </IconButton>
                    <IconButton disabled={isReadOnly} size="small" title="Mark as clean" onClick={getMarkAsCleanFn()}>
                        <AutoFixNormalIcon sx={{ fontSize: 18 }} />
                    </IconButton>
                    <IconButton
                        disabled={isReadOnly}
                        size="small"
                        title="Mark as clean and propagate"
                        onClick={getMarkAsCleanFn(true)}
                    >
                        <AutoFixHighIcon sx={{ fontSize: 18 }} />
                    </IconButton>
                </Grid>
            </React.Fragment>
        );
    };

    return (
        <>
            <Grid item xs={12}>
                <Typography variant="subtitle1">Dirty</Typography>
            </Grid>
            {link.dirty ? (
                getResourceElm({
                    resource: link.target,
                    lastCleanVersion: link.lastCleanVersion,
                    isDirectDirtiness: true,
                })
            ) : (
                <Grid item xs={12}>
                    <Typography variant="caption">Link has no direct dirty resource</Typography>
                </Grid>
            )}

            <Grid item xs={12}>
                <Typography variant="subtitle1">Inferred Dirtiness</Typography>
            </Grid>
            {link.inferredDirtiness.length === 0 ? (
                <Grid item xs={12}>
                    <Typography variant="caption">Link has no inferred dirtiness</Typography>
                </Grid>
            ) : (
                link.inferredDirtiness.map(getResourceElm)
            )}
        </>
    );
}
