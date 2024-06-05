/* eslint-disable react/jsx-no-bind */
import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
// @mui
import { Button, Grid, Divider, Typography, IconButton } from '@mui/material';
import { OpenInNew as OpenInNewIcon, Insights as InsightsIcon } from '@mui/icons-material';
// components
import DirtinessSection from './DirtinessSection';
// utils
import { COLORS } from '../../theme';
import { SelectionEntry } from '../../depiTypes';

// ----------------------------------------------------------------------
ResourceLinkForm.propTypes = {
    isBlackboardEmpty: PropTypes.bool,
    isReadOnly: PropTypes.bool,
    selection: PropTypes.arrayOf(SelectionEntry).isRequired,
    // Actions
    onRevealInEditor: PropTypes.func.isRequired,
    onViewResourceDiff: PropTypes.func.isRequired,
    onRemoveEntriesFromBlackboard: PropTypes.func.isRequired,
    onDeleteEntriesFromDepi: PropTypes.func.isRequired,
    onMarkLinksClean: PropTypes.func.isRequired,
    onMarkInferredDirtinessClean: PropTypes.func.isRequired,
    onMarkAllClean: PropTypes.func.isRequired,
    onShowDependencyGraph: PropTypes.func.isRequired,
};

export default function ResourceLinkForm({
    isBlackboardEmpty,
    isReadOnly,
    selection,
    onRevealInEditor,
    onViewResourceDiff,
    onRemoveEntriesFromBlackboard,
    onDeleteEntriesFromDepi,
    onMarkLinksClean,
    onMarkInferredDirtinessClean,
    onMarkAllClean,
    onShowDependencyGraph,
}) {
    const {
        allOnBlackboard,
        allInDepi,
        onlyLinks,
        resources,
        links,
        dirtySelectedLinks,
        dirtyResources,
        dependsOnDirtyResources,
    } = useMemo(() => {
        const resourceEntries = selection.filter(({ isLink }) => !isLink);
        const resources = resourceEntries.map(({ entry }) => entry);
        const links = selection.filter(({ isLink }) => isLink).map(({ entry }) => entry);
        const dirtySelectedLinks = links.filter((link) => link.dirty || link.inferredDirtiness.length > 0);
        const onlyLinks = resources.length === 0;
        const onlyResources = links.length === 0;

        const allOnBlackboard = !selection.some(({ onBlackboard }) => !onBlackboard);
        const allInDepi = !selection.some(({ inDepi }) => !inDepi);
        const someOnBlackboard = selection.some(({ onBlackboard }) => onBlackboard);
        const someInDepi = selection.some(({ inDepi }) => inDepi);

        const dirtyResources = new Set();
        const dependsOnDirtyResources = new Set();

        resourceEntries.forEach(({ isDirty, dependsOnDirty, entry }) => {
            if (isDirty) {
                dirtyResources.add(entry);
            }

            if (dependsOnDirty) {
                dependsOnDirtyResources.add(entry);
            }
        });

        return {
            allOnBlackboard,
            allInDepi,
            someInDepi,
            someOnBlackboard,
            onlyLinks,
            onlyResources,
            resources,
            links,
            dirtySelectedLinks,
            dirtyResources,
            dependsOnDirtyResources,
        };
    }, [selection]);

    const isMulti = selection.length > 1;

    let deleteHelpMessage = '';

    if (!allInDepi) {
        deleteHelpMessage = `Entr${isMulti ? 'ies' : 'y'} not in depi.`;
    } else if (!isBlackboardEmpty) {
        deleteHelpMessage = `Entr${isMulti ? 'ies' : 'y'} can only be deleted when blackboard is empty.`;
    } else {
        deleteHelpMessage = `Entr${isMulti ? 'ies' : 'y'} will be deleted from depi.`;
    }

    return (
        <Grid container spacing={2} style={{ padding: 10 }}>
            {resources.map((resource) => (
                <Grid
                    item
                    xs={12}
                    key={`${resource.resourceGroupUrl}#${resource.url}`}
                    style={{ position: 'relative' }}
                >
                    <Grid container spacing={1}>
                        <IconButton
                            title="Reveal resource"
                            style={{ position: 'absolute', top: 10, right: 0 }}
                            onClick={() => onRevealInEditor(resource)}
                        >
                            <OpenInNewIcon />
                        </IconButton>
                        <IconButton
                            title="Show dependency graph"
                            style={{ position: 'absolute', top: 50, right: 0 }}
                            onClick={() => onShowDependencyGraph(resource)}
                        >
                            <InsightsIcon />
                        </IconButton>

                        <Grid item xs={12}>
                            <Typography variant="h6">{resource.name}</Typography>
                        </Grid>
                        {dirtyResources.has(resource) ? (
                            <Grid item xs={12}>
                                <Typography variant="caption" sx={{ color: COLORS.DIRTY }}>
                                    Resource has changed and is considered dirty.
                                </Typography>
                            </Grid>
                        ) : null}
                        {dependsOnDirtyResources.has(resource) ? (
                            <Grid item xs={12}>
                                <Typography variant="caption" sx={{ color: COLORS.DEPENDS_ON_DIRTY }}>
                                    Resource depends on dirty resources.
                                </Typography>
                            </Grid>
                        ) : null}
                        <Grid item xs={2}>
                            <Typography variant="body2">ID:</Typography>
                        </Grid>
                        <Grid item xs={10}>
                            <Typography variant="body2">{resource.id}</Typography>
                        </Grid>
                        <Grid item xs={2}>
                            <Typography variant="body2">URL:</Typography>
                        </Grid>
                        <Grid item xs={10}>
                            <Typography variant="body2">{resource.url}</Typography>
                        </Grid>
                        <Grid item xs={2}>
                            <Typography variant="body2">Tool:</Typography>
                        </Grid>
                        <Grid item xs={10}>
                            <Typography variant="body2">{resource.toolId}</Typography>
                        </Grid>
                        <Grid item xs={12}>
                            <Typography variant="body2">Resource Group URL:</Typography>
                        </Grid>
                        <Grid item xs={1} />
                        <Grid item xs={11}>
                            <Typography variant="caption">{resource.resourceGroupUrl}</Typography>
                        </Grid>
                        <Grid item xs={12}>
                            <Typography variant="body2">Resource Group Version:</Typography>
                        </Grid>
                        <Grid item xs={1} />
                        <Grid item xs={11}>
                            <Typography variant="caption" sx={{ color: 'grey', fontSize: '11px' }}>
                                {resource.resourceGroupVersion}
                            </Typography>
                        </Grid>
                    </Grid>
                    <Grid sx={{ marginTop: 1 }} item xs={12}>
                        <Divider />
                    </Grid>
                </Grid>
            ))}

            {links.map((link) => (
                <Grid
                    item
                    xs={12}
                    key={`${link.source.resourceGroupUrl}#${link.source.url}-->${link.target.resourceGroupUrl}#${link.target.url}`}
                    style={{ position: 'relative' }}
                >
                    <Grid container spacing={1}>
                        <Grid item xs={12}>
                            <Typography variant="subtitle1">{link.source.name}</Typography>
                        </Grid>
                        <Grid item xs={1} />
                        <Grid item xs={2}>
                            <Typography variant="body2">URL:</Typography>
                        </Grid>
                        <Grid item xs={9}>
                            <Typography variant="body2">{link.source.url}</Typography>
                        </Grid>
                        <Grid item xs={1} />
                        <Grid item xs={2}>
                            <Typography variant="body2">Tool:</Typography>
                        </Grid>
                        <Grid item xs={9}>
                            <Typography variant="body2">{link.source.toolId}</Typography>
                        </Grid>
                        <Grid item xs={1} />
                        <Grid item xs={11}>
                            <Typography variant="caption">{link.source.resourceGroupUrl}</Typography>
                        </Grid>
                        <Grid item xs={1} />
                        <Grid item xs={11}>
                            <Typography variant="caption" sx={{ color: 'grey', fontSize: '11px' }}>
                                {link.source.resourceGroupVersion}
                            </Typography>
                        </Grid>
                        <Grid item xs={12} sx={{ textAlign: 'center', color: COLORS.DEPI_EDGE, marginTop: 2 }}>
                            <Typography variant="overline"> {'-- Depends on -->'}</Typography>
                        </Grid>
                        <Grid item xs={12}>
                            <Typography variant="subtitle1">{link.target.name}</Typography>
                        </Grid>
                        <Grid item xs={1} />
                        <Grid item xs={2}>
                            <Typography variant="body2">URL:</Typography>
                        </Grid>
                        <Grid item xs={9}>
                            <Typography variant="body2">{link.target.url}</Typography>
                        </Grid>
                        <Grid item xs={1} />
                        <Grid item xs={2}>
                            <Typography variant="body2">Tool:</Typography>
                        </Grid>
                        <Grid item xs={9}>
                            <Typography variant="body2">{link.target.toolId}</Typography>
                        </Grid>
                        <Grid item xs={1} />
                        <Grid item xs={11}>
                            <Typography variant="caption">{link.target.resourceGroupUrl}</Typography>
                        </Grid>
                        <Grid item xs={1} />
                        <Grid item xs={11}>
                            <Typography variant="caption" sx={{ color: 'grey', fontSize: '11px' }}>
                                {link.target.resourceGroupVersion}
                            </Typography>
                        </Grid>
                    </Grid>
                    <Grid sx={{ marginTop: 1 }} item xs={12}>
                        <Divider />
                    </Grid>
                </Grid>
            ))}

            {onlyLinks && links.length === 1 && dirtySelectedLinks.length === 1 ? (
                <DirtinessSection
                    isReadOnly={isReadOnly}
                    link={dirtySelectedLinks[0]}
                    onRevealInEditor={onRevealInEditor}
                    onViewResourceDiff={onViewResourceDiff}
                    onMarkLinksClean={onMarkLinksClean}
                    onMarkInferredDirtinessClean={onMarkInferredDirtinessClean}
                />
            ) : null}

            {onlyLinks && dirtySelectedLinks.length > 0 ? (
                <Grid item xs={12}>
                    <Button
                        disabled={isReadOnly}
                        aria-label="mark-as-clean"
                        onClick={() => onMarkAllClean(dirtySelectedLinks)}
                    >
                        Mark Links all Clean
                    </Button>
                    <br />
                    <Typography sx={{ ml: 2, color: 'grey' }} variant="caption">
                        {`Any dirtiness on the selected dirty links will be cleaned up.`}
                    </Typography>
                </Grid>
            ) : null}

            {selection.length > 0 ? (
                <>
                    <Grid item xs={12}>
                        <Button
                            aria-label="remove"
                            disabled={isReadOnly || !allOnBlackboard}
                            onClick={() => onRemoveEntriesFromBlackboard(selection)}
                        >
                            Remove from Blackboard
                        </Button>
                        <br />
                        <Typography sx={{ ml: 2, color: 'grey' }} variant="caption">
                            {allOnBlackboard
                                ? `Entr${isMulti ? 'ies' : 'y'} will be removed from current blackboard.`
                                : `${isMulti ? 'Some e' : 'E'}ntr${isMulti ? 'ies' : 'y'} not on blackboard.`}
                        </Typography>
                    </Grid>
                    <Grid item xs={12}>
                        <Button
                            aria-label="delete"
                            disabled={isReadOnly || !allInDepi || !isBlackboardEmpty}
                            onClick={() => onDeleteEntriesFromDepi(selection)}
                        >
                            Delete from Depi
                        </Button>
                        <br />
                        <Typography sx={{ ml: 2, color: 'grey' }} variant="caption">
                            {deleteHelpMessage}
                        </Typography>
                    </Grid>
                </>
            ) : (
                <Grid item xs={12}>
                    <Typography sx={{ ml: 2, color: 'grey' }} variant="caption">
                        No Selection ...
                    </Typography>
                </Grid>
            )}
        </Grid>
    );
}
