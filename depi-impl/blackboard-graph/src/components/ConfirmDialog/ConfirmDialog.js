import PropTypes from 'prop-types';
import React from 'react';
// @mui
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import Button from '@mui/material/Button';

ConfirmModal.propTypes = {
    open: PropTypes.bool,
    title: PropTypes.string,
    text: PropTypes.string,
    onClose: PropTypes.func.isRequired,
};

export default function ConfirmModal({ open, title = 'Confirm', text = 'Are you sure you want to proceed?', onClose }) {
    const handleOkClick = () => {
        onClose(true);
    };

    const handleCancelClick = () => {
        onClose();
    };

    return (
        <Dialog
            open={open}
            onClose={() => {
                onClose();
            }}
        >
            <DialogTitle>{title}</DialogTitle>
            <DialogContent>
                <DialogContentText>{text}</DialogContentText>
            </DialogContent>
            <DialogActions>
                <Button onClick={handleCancelClick} color="secondary">
                    Cancel
                </Button>
                <Button onClick={handleOkClick} color="primary">
                    OK
                </Button>
            </DialogActions>
        </Dialog>
    );
}
