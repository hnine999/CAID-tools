import PropTypes from 'prop-types';
import React from 'react';
// @mui
import { Box, Grid, Fab, Typography } from '@mui/material';
import { Save as SaveIcon, Clear as ClearIcon } from '@mui/icons-material';
// utils
import { BlackboardModel } from '../../depiTypes';
import { COLORS } from '../../theme';

BlackboardAppBarDetails.propTypes = {
    isReadOnly: PropTypes.bool,
    blackboardModel: BlackboardModel,
    onSaveBlackboard: PropTypes.func.isRequired,
    onClearBlackboard: PropTypes.func.isRequired,
};

export default function BlackboardAppBarDetails({ isReadOnly, blackboardModel, onSaveBlackboard, onClearBlackboard }) {
    const nbrOfResources = blackboardModel.resources.length;
    const nbrOfLinks = blackboardModel.links.length;

    return (
        <>
            <Box sx={{ flexGrow: 1, marginLeft: 2, color: COLORS.LIGHT_GREY }}>
                {nbrOfResources + nbrOfLinks === 0 ? (
                    <Typography variant="body2">{isReadOnly ? 'Editing disabled' : 'No changes'}</Typography>
                ) : (
                    <Grid container spacing={2}>
                        <Grid item>
                            <Typography variant="body2">Number of Resources: {nbrOfResources}</Typography>
                            <Typography variant="body2">Number of Links: {nbrOfLinks}</Typography>
                        </Grid>
                        <Grid item>
                            <Fab
                                variant="extended"
                                color="primary"
                                aria-label="save"
                                size="small"
                                onClick={onSaveBlackboard}
                            >
                                <SaveIcon />
                                SAVE
                            </Fab>
                        </Grid>
                        <Grid item>
                            <Fab
                                variant="extended"
                                color="default"
                                aria-label="clear"
                                size="small"
                                onClick={onClearBlackboard}
                            >
                                <ClearIcon />
                                CLEAR
                            </Fab>
                        </Grid>
                    </Grid>
                )}
            </Box>
        </>
    );
}
