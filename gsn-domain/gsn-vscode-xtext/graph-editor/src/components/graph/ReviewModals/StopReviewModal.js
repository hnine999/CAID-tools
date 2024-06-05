import PropTypes from 'prop-types';
import React, { useMemo } from 'react';
// @mui
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import Button from '@mui/material/Button';
// utils
import { NodeType } from '../gsnTypes';
import GSN_CONSTANTS from '../GSN_CONSTANTS';

StopReviewModal.propTypes = {
    model: PropTypes.arrayOf(NodeType).isRequired,
    reviewTag: PropTypes.string.isRequired,
    open: PropTypes.bool,
    onClose: PropTypes.func.isRequired,
};

export default function StopReviewModal({ model, reviewTag, open, onClose }) {
    const [hasUnreviewedNodes, nbrOfGoals, nbrOfSolutions] = useMemo(() => {
        let goals = 0;
        let solutions = 0;

        if (!open) {
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
    }, [model, open]);

    const handleSubmitClick = () => {
        onClose(true, reviewTag);
    };

    const handleAbortClick = () => {
        onClose(false, reviewTag);
    };

    const handleCloseClick = () => {
        onClose();
    };

    return (
        <Dialog open={open} onClose={onClose}>
            <DialogTitle>Submit review {reviewTag}</DialogTitle>
            <DialogContent>
                <DialogContentText>
                    Submit or Abort the current review.
                    <ul>
                        <li>Submit will create a git-tag: {reviewTag}.</li>
                        <li>Abort will delete the review related information from this repository.</li>
                    </ul>
                    {hasUnreviewedNodes ? (
                        <>
                            <br />
                            {`Currently the model has ${
                                nbrOfGoals + nbrOfSolutions
                            } unreviewed nodes and you may not submit the review untill these have been transitioned.`}
                        </>
                    ) : null}
                </DialogContentText>
            </DialogContent>
            <DialogActions>
                <Button onClick={handleCloseClick} color="primary">
                    Close
                </Button>
                <Button onClick={handleAbortClick} color="error">
                    Abort
                </Button>
                <Button disabled={hasUnreviewedNodes} onClick={handleSubmitClick} color="primary">
                    Submit
                </Button>
            </DialogActions>
        </Dialog>
    );
}
