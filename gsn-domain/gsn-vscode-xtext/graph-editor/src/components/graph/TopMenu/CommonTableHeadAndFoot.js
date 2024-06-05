import PropTypes from 'prop-types';
import React, { useMemo } from 'react';
// @mui
import { Button, Grid, TextField, TablePagination } from '@mui/material';

CommonTableHeadAndFoot.propTypes = {
    isReadOnly: PropTypes.bool,
    rowCount: PropTypes.number,
    pageIndex: PropTypes.number,
    pageSize: PropTypes.number,
    searchTerm: PropTypes.string,
    setSearchTerm: PropTypes.func.isRequired,
    setPageIndex: PropTypes.func.isRequired,
    setPageSize: PropTypes.func.isRequired,
    children: PropTypes.element,
    // Optional Editing/Adding stuff.
    isAdding: PropTypes.bool,
    setEditData: PropTypes.func,
    onAddClick: PropTypes.func,
    onSaveAdd: PropTypes.func,
    onCancelAdd: PropTypes.func,
    editingId: PropTypes.string,
    editData: PropTypes.shape({
        name: PropTypes.string,
        description: PropTypes.string,
    }),
};

export default function CommonTableHeadAndFoot({
    isReadOnly,
    rowCount,
    pageIndex,
    pageSize,
    searchTerm,
    setSearchTerm,
    setPageIndex,
    setPageSize,
    children,
    // Optional Editing/Adding stuff.
    isAdding,
    editingId,
    editData,
    onAddClick,
    onSaveAdd,
    onCancelAdd,
    setEditData,
}) {
    const header = useMemo(
        () =>
            isAdding ? (
                <Grid
                    container
                    justifyContent="space-between"
                    alignItems="center"
                    sx={{ backgroundColor: 'rgb(166 166 200 / 20%)', borderRadius: '10px', padding: '10px' }}
                >
                    <Grid item>
                        <TextField
                            size="small"
                            margin="dense"
                            label="Name"
                            value={editData.name}
                            onChange={(e) => setEditData({ ...editData, name: e.target.value })}
                        />
                    </Grid>
                    <Grid item>
                        <TextField
                            size="small"
                            margin="dense"
                            label="Optional Description"
                            value={editData.description}
                            onChange={(e) => setEditData({ ...editData, description: e.target.value })}
                        />
                    </Grid>
                    <Grid item>
                        <Button onClick={() => onSaveAdd()}>SAVE</Button>
                        <Button onClick={onCancelAdd}>CANCEL</Button>
                    </Grid>
                </Grid>
            ) : (
                <Grid container justifyContent="space-between" alignItems="center">
                    <Grid item>
                        <TextField
                            key="search-field"
                            size="small"
                            margin="dense"
                            label="Search"
                            value={searchTerm}
                            onChange={(e) => {
                                setSearchTerm(e.target.value.toLowerCase());
                                setPageIndex(0);
                            }}
                        />
                    </Grid>
                    {typeof onAddClick !== 'function' ? null : (
                        <Grid item>
                            <Button
                                disabled={isReadOnly || Boolean(editingId)}
                                onClick={onAddClick}
                                variant="contained"
                                color="success"
                            >
                                + ADD
                            </Button>
                        </Grid>
                    )}
                </Grid>
            ),
        [
            isAdding,
            setEditData,
            onSaveAdd,
            onAddClick,
            onCancelAdd,
            setSearchTerm,
            searchTerm,
            setPageIndex,
            isReadOnly,
            editingId,
            editData,
        ]
    );

    return (
        <Grid container sx={{ paddingX: 2 }}>
            {header}
            {children}

            <TablePagination
                component="div"
                count={rowCount}
                page={pageIndex}
                onPageChange={(_, newPage) => setPageIndex(newPage)}
                rowsPerPage={pageSize}
                onRowsPerPageChange={(event) => setPageSize(parseInt(event.target.value, 10))}
            />
        </Grid>
    );
}
