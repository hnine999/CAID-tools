/* eslint-disable react/jsx-no-bind */
import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
// @mui
import { Button, Grid, Divider, TextField, Typography, IconButton } from '@mui/material';
import { Edit as EditIcon } from '@mui/icons-material';
// components
import ConfirmDialog from '../ConfirmDialog';
// utils
import useAwaitableComponent from '../../hooks/useAwaitableComponent';
import { ResourceGroup } from '../../depiTypes';

// ----------------------------------------------------------------------
ResourceGroupForm.propTypes = {
    isBlackboardEmpty: PropTypes.bool,
    isReadOnly: PropTypes.bool,
    resourceGroup: ResourceGroup.isRequired,
    // Actions
    onEditResourceGroup: PropTypes.func.isRequired,
};

const REMOVE_TITLE = 'Confirm Removal';
const UPDATE_TITLE = 'Confirm Update';

const REMOVE_TEXT =
    'Removing the resource-group will delete all contained resources and all the incoming and outgoing links. Are you sure you want to proceed?';
const UPDATE_TEXT = 'Updating the tool and/or URL of resource-group will update all related resources and links.';

export default function ResourceGroupForm({ isBlackboardEmpty, isReadOnly, resourceGroup, onEditResourceGroup }) {
    const [editMode, setEditMode] = useState(false);
    const [editState, setEditState] = useState({
        hasChanges: false,
        error: '',
        name: '',
        url: '',
        toolId: '',
        version: '',
    });

    const [dialogInfo, setDialogInfo] = useState({ title: '', text: '' });
    const [status, execute, resolve, reset] = useAwaitableComponent();
    const dialogOpen = status === 'awaiting';

    useEffect(() => {
        if (editMode) {
            setEditState({
                hasChanges: false,
                error: '',
                ...resourceGroup,
            });
        }
    }, [editMode, resourceGroup]);

    useEffect(() => {
        setEditMode(false);
    }, [resourceGroup]);

    const handleInputChange = useCallback((event, key) => {
        setEditState((prevState) => ({
            ...prevState,
            [key]: event.target.value,
            hasChanges: true,
            error: prevState.error || (event.target.value === '' ? 'Value cannot be empty!' : ''),
        }));
    }, []);

    async function onUpdate() {
        let proceed;
        if (editState.toolId !== resourceGroup.toolId || editState.url !== resourceGroup.url) {
            setDialogInfo({ title: UPDATE_TITLE, text: UPDATE_TEXT });
            proceed = await execute();
        } else {
            proceed = true;
        }

        if (proceed) {
            onEditResourceGroup(
                { url: resourceGroup.url, toolId: resourceGroup.toolId },
                {
                    name: editState.name,
                    url: editState.url,
                    toolId: editState.toolId,
                    version: editState.version,
                },
                false
            );
        }
        reset();
        setEditMode(false);
    }

    async function onDelete() {
        setDialogInfo({ title: REMOVE_TITLE, text: REMOVE_TEXT });
        const proceed = await execute();
        if (proceed) {
            onEditResourceGroup({ url: resourceGroup.url, toolId: resourceGroup.toolId }, null, true);
        }
        reset();
        setEditMode(false);
    }

    const editDisabled = isReadOnly || !isBlackboardEmpty;

    return (
        <Grid container spacing={2} style={{ padding: 10 }}>
            <Grid item xs={12} style={{ position: 'relative' }}>
                <Grid container spacing={1}>
                    {editMode ? null : (
                        <IconButton
                            disabled={editDisabled}
                            title={
                                editDisabled ? 'Edit resource group properties' : 'Blackboard must be empty to edit ..'
                            }
                            style={{ position: 'absolute', top: 10, right: 0 }}
                            onClick={() => setEditMode(true)}
                        >
                            <EditIcon />
                        </IconButton>
                    )}
                    {editMode ? (
                        <EditTextField
                            autoFocus
                            name="name"
                            value={editState.name}
                            handleInputChange={handleInputChange}
                        />
                    ) : (
                        <Grid item xs={12}>
                            <Typography variant="h6">{resourceGroup.name}</Typography>
                        </Grid>
                    )}
                    {editMode ? (
                        <EditTextField name="toolId" value={editState.toolId} handleInputChange={handleInputChange} />
                    ) : (
                        <>
                            <Grid item xs={2}>
                                <Typography variant="body2">Tool:</Typography>
                            </Grid>
                            <Grid item xs={10}>
                                <Typography variant="body2">{resourceGroup.toolId}</Typography>
                            </Grid>
                        </>
                    )}
                    {editMode ? (
                        <EditTextField name="url" value={editState.url} handleInputChange={handleInputChange} />
                    ) : (
                        <>
                            <Grid item xs={12}>
                                <Typography variant="body2">URL:</Typography>
                            </Grid>
                            <Grid item xs={1} />
                            <Grid item xs={11}>
                                <Typography variant="caption">{resourceGroup.url}</Typography>
                            </Grid>
                        </>
                    )}
                    {editMode ? (
                        <EditTextField name="version" value={editState.version} handleInputChange={handleInputChange} />
                    ) : (
                        <>
                            <Grid item xs={12}>
                                <Typography variant="body2">Version:</Typography>
                            </Grid>
                            <Grid item xs={1} />
                            <Grid item xs={11}>
                                <Typography variant="caption" sx={{ color: 'grey', fontSize: '11px' }}>
                                    {resourceGroup.version}
                                </Typography>
                            </Grid>
                        </>
                    )}
                </Grid>
                <Grid sx={{ marginTop: 1, marginBottom: 1 }} item xs={12}>
                    <Divider />
                </Grid>
                {editMode ? (
                    <>
                        <Grid item xs={12}>
                            <Typography variant="caption" sx={{ color: 'red', fontSize: '11px' }}>
                                {editState.error}
                            </Typography>
                        </Grid>
                        <Grid item xs={12} />
                        <Grid item xs={12}>
                            <Grid container spacing={1} justifyContent="flex-end">
                                <Grid item>
                                    <Button size="small" variant="outlined" color="error" onClick={() => onDelete()}>
                                        Delete
                                    </Button>
                                </Grid>
                                <Grid item>
                                    <Button
                                        size="small"
                                        variant="outlined"
                                        color="secondary"
                                        onClick={() => setEditMode(false)}
                                    >
                                        Cancel
                                    </Button>
                                </Grid>
                                <Grid item>
                                    <Button
                                        size="small"
                                        variant="outlined"
                                        color="primary"
                                        disabled={!editState.hasChanges || Boolean(editState.error)}
                                        onClick={() => onUpdate()}
                                    >
                                        Update
                                    </Button>
                                </Grid>
                            </Grid>
                        </Grid>
                    </>
                ) : null}
            </Grid>
            <ConfirmDialog open={dialogOpen} onClose={resolve} title={dialogInfo.title} text={dialogInfo.text} />
        </Grid>
    );
}

EditTextField.propTypes = {
    name: PropTypes.string.isRequired,
    autoFocus: PropTypes.bool,
    value: PropTypes.string.isRequired,
    handleInputChange: PropTypes.func.isRequired,
};

function EditTextField({ name, value, handleInputChange, autoFocus = false }) {
    return (
        <TextField
            autoFocus={autoFocus}
            size="small"
            margin="dense"
            id={name}
            label={name.charAt(0).toUpperCase() + name.slice(1)}
            fullWidth
            sx={{ '& input': { fontSize: '11px' } }}
            value={value}
            onChange={(event) => handleInputChange(event, name)}
        />
    );
}
