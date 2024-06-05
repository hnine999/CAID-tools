import PropTypes from 'prop-types';
import React from 'react';
// @mui
import { Box, AppBar, IconButton, Typography, Toolbar } from '@mui/material';
import {
    Refresh as RefreshIcon,
    PlayArrow as PlayArrowIcon,
    PlayDisabled as PlayDisabledIcon,
    Lock as LockIcon,
} from '@mui/icons-material';
// components
import DependencyAppBarDetails from './DependencyAppBarDetails';
import BlackboardAppBarDetails from './BlackboardAppBarDetails';
import BranchSelector from '../BranchSelector';
// utils
import { BlackboardModel, Resource } from '../../depiTypes';
import { COLORS } from '../../theme';

AppBarHeader.propTypes = {
    isReadOnly: PropTypes.bool,
    layoutOpts: PropTypes.shape({
        headerHeight: PropTypes.number.isRequired,
    }).isRequired,
    branchName: PropTypes.string,
    branchesAndTags: PropTypes.shape({
        branches: PropTypes.arrayOf(PropTypes.string),
        tags: PropTypes.arrayOf(PropTypes.string),
    }),
    resource: Resource,
    dependants: PropTypes.bool,
    blackboardModel: BlackboardModel,
    showDirtyness: PropTypes.bool,
    setShowDirtyness: PropTypes.func.isRequired,
    onSaveBlackboard: PropTypes.func.isRequired,
    onClearBlackboard: PropTypes.func.isRequired,
    onRefreshModel: PropTypes.func.isRequired,
    onShowBlackboard: PropTypes.func.isRequired,
    onShowDependencyGraph: PropTypes.func.isRequired,
    onSwitchBranch: PropTypes.func.isRequired,
};

export default function AppBarHeader({
    isReadOnly,
    layoutOpts,
    branchName,
    branchesAndTags,
    resource,
    dependants,
    blackboardModel,
    showDirtyness,
    setShowDirtyness,
    onSaveBlackboard,
    onClearBlackboard,
    onRefreshModel,
    onShowBlackboard,
    onShowDependencyGraph,
    onSwitchBranch,
}) {
    const height = layoutOpts.headerHeight;
    const isBlackboard = !resource;

    function AnimationToggle() {
        if (showDirtyness) {
            return (
                <IconButton title="Stop Animation" color="info" onClick={() => setShowDirtyness(false)}>
                    <PlayDisabledIcon />
                </IconButton>
            );
        }

        return (
            <IconButton title="Animate Dirtyness" color="info" onClick={() => setShowDirtyness(true)}>
                <PlayArrowIcon />
            </IconButton>
        );
    }

    let title = 'DEPI BLACKBOARD';
    if (!isBlackboard) {
        title = dependants ? 'DEPENDANTS GRAPH' : 'DEPENDENCY GRAPH';
    }

    return (
        <Box sx={{ flexGrow: 1 }}>
            <AppBar
                position="static"
                color="primary"
                style={{
                    minHeight: height,
                    maxHeight: height,
                    height,
                    backgroundColor: isBlackboard ? '#494848' : 'rgb(0 75 119)',
                }}
            >
                <Toolbar>
                    <Typography variant="h6" component="div" sx={{ color: COLORS.LIGHT_GREY, paddingRight: 1 }}>
                        {title}
                    </Typography>
                    {isReadOnly ? <LockIcon sx={{ color: COLORS.LIGHT_GREY }} /> : null}
                    {isBlackboard ? (
                        <BlackboardAppBarDetails
                            isReadOnly={isReadOnly}
                            blackboardModel={blackboardModel}
                            showDirtyness={showDirtyness}
                            onSaveBlackboard={onSaveBlackboard}
                            onClearBlackboard={onClearBlackboard}
                            setShowDirtyness={setShowDirtyness}
                        />
                    ) : (
                        <DependencyAppBarDetails
                            resource={resource}
                            dependants={dependants}
                            onShowBlackboard={onShowBlackboard}
                            onShowDependencyGraph={onShowDependencyGraph}
                        />
                    )}
                    <IconButton color="info" onClick={() => onRefreshModel()} title="Refresh models">
                        <RefreshIcon />
                    </IconButton>
                    <AnimationToggle />
                    <BranchSelector
                        branchName={branchName}
                        branchesAndTags={branchesAndTags}
                        onSwitchBranch={onSwitchBranch}
                    />
                </Toolbar>
            </AppBar>
        </Box>
    );
}
