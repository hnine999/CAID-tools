import PropTypes from 'prop-types';
import React, { useState } from 'react';
// @mui
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';

StartReviewModal.propTypes = {
    open: PropTypes.bool,
    onClose: PropTypes.func.isRequired,
};

export default function StartReviewModal({ open, onClose }) {
    const [inputValue, setInputValue] = useState('');

    const handleInputChange = (event) => {
        setInputValue(event.target.value);
    };

    const handleOkClick = () => {
        onClose(inputValue);
    };

    const handleCancelClick = () => {
        onClose();
    };

    return (
        <Dialog open={open} onClose={onClose}>
            <DialogTitle>Start new Review</DialogTitle>
            <DialogContent>
                <DialogContentText>Enter tag/branch name (e.g v0.1.0):</DialogContentText>
                <TextField
                    autoFocus
                    margin="dense"
                    id="inputField"
                    label="String"
                    fullWidth
                    value={inputValue}
                    onChange={handleInputChange}
                />
            </DialogContent>
            <DialogActions>
                <Button onClick={handleCancelClick} color="primary">
                    Cancel
                </Button>
                <Button onClick={handleOkClick} color="primary">
                    OK
                </Button>
            </DialogActions>
        </Dialog>
    );
}
