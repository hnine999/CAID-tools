import PropTypes from 'prop-types';
import React from 'react';
// @mui
import { Box, IconButton, Typography } from '@mui/material';
import { AccountTree as AccountTreeIcon, SwapHoriz as SwapHorizIcon } from '@mui/icons-material';
// utils
import { Resource } from '../../depiTypes';
import { COLORS } from '../../theme';

DependencyAppBarDetails.propTypes = {
    resource: Resource,
    dependants: PropTypes.bool,
    onShowDependencyGraph: PropTypes.func.isRequired,
    onShowBlackboard: PropTypes.func.isRequired,
};

export default function DependencyAppBarDetails({ resource, dependants, onShowBlackboard, onShowDependencyGraph }) {
    const switchDirection = () => {
        onShowDependencyGraph(resource, !dependants);
    };

    return (
        <>
            <Box sx={{ flexGrow: 1, marginLeft: 2, color: COLORS.LIGHT_GREY }}>
                {!resource ? <Typography variant="body2">No resource ..</Typography> : null}
            </Box>
            <IconButton color="info" onClick={() => onShowBlackboard()} title="Show blackboard">
                <AccountTreeIcon />
            </IconButton>
            <IconButton
                color="info"
                onClick={switchDirection}
                title={dependants ? 'Switch to Dependencies' : 'Switch to Dependants'}
            >
                <SwapHorizIcon />
            </IconButton>
        </>
    );
}
