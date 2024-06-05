import PropTypes from 'prop-types';
import { useMemo } from 'react';
import { Typography, Grid } from '@mui/material';
import CopyrightVandy from '../CopyrightVandy';
// utils
import { NodeType } from '../gsnTypes';
import GSN_CONSTANTS from '../GSN_CONSTANTS';

NoSelectionInfo.propTypes = {
    reviewTag: PropTypes.string,
    model: PropTypes.arrayOf(NodeType).isRequired,
};

export default function NoSelectionInfo({ reviewTag, model }) {
    const [nbrOfGoals, nbrOfSolutions] = useMemo(() => {
        let goals = 0;
        let solutions = 0;

        if (!reviewTag) {
            return [false, goals, solutions];
        }

        const isNotReviewed = (node) => !node.status || node.status === GSN_CONSTANTS.NODE_STATUS_OPTIONS.NOT_REVIEWED;

        model.forEach((node) => {
            if (node.type === GSN_CONSTANTS.TYPES.SOLUTION && isNotReviewed(node)) {
                solutions += 1;
            } else if (node.type === GSN_CONSTANTS.TYPES.GOAL && isNotReviewed(node)) {
                goals += 1;
            }
        });

        return [goals + solutions > 0, goals, solutions];
    }, [model, reviewTag]);

    return (
        <>
            <Grid container spacing={2} style={{ padding: 10 }}>
                {reviewTag ? (
                    <Grid item xs={12} sx={{ alignItems: 'center', display: 'flex', justifyContent: 'center' }}>
                        <Typography variant="h5" component="div">
                            In review {reviewTag}
                        </Typography>
                    </Grid>
                ) : (
                    <Grid item xs={12}>
                        <Typography variant="h5" component="div">
                            GSN Assurance
                        </Typography>
                    </Grid>
                )}
                <Grid item xs={12}>
                    <Typography variant="body2" component="div">
                        {reviewTag
                            ? 'This model is in a review state. Transition the Goals and Solutions nodes into a reviewed state (Approved or Disapproved).'
                            : 'Navigate down the assurance case tree by expanding the sub-goals. Holding down Ctrl will expand/collapse all sub-goals recurisvely.'}
                    </Typography>
                </Grid>
                <Grid item xs={12}>
                    <Typography variant="body2" component="div">
                        {reviewTag ? (
                            <>
                                Currently the model has <b>{nbrOfGoals + nbrOfSolutions}</b> unreviewed node(s).
                            </>
                        ) : (
                            'Use the control-menu (bottom left corner) for additional actions, e.g. expand all nodes, export graph as svg, fit screen, etc.'
                        )}
                    </Typography>
                </Grid>
            </Grid>
            <CopyrightVandy />
        </>
    );
}
