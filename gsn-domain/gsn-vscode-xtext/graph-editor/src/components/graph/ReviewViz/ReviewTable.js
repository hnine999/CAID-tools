import PropTypes from 'prop-types';
import React, { useState, useCallback } from 'react';
// @mui
import { Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper } from '@mui/material';
// components
import CommonTableHeadAndFoot from '../TopMenu/CommonTableHeadAndFoot';
// utils
import ReviewTableRow from './ReviewTableRow';
import { DepiMethodsType } from '../gsnTypes';

ReviewTable.propTypes = {
    isReadOnly: PropTypes.bool,
    showState: PropTypes.bool,
    showStatus: PropTypes.bool,
    showSummary: PropTypes.bool,
    showReview: PropTypes.bool,
    showUuid: PropTypes.bool,
    data: PropTypes.arrayOf(PropTypes.object).isRequired,
    expandedRows: PropTypes.arrayOf(PropTypes.string).isRequired,
    height: PropTypes.number.isRequired,
    selectedNode: PropTypes.oneOfType([
        PropTypes.shape({
            nodeId: PropTypes.string,
            treeId: PropTypes.string,
        }),
        PropTypes.arrayOf(PropTypes.string),
    ]),
    setSelectedNode: PropTypes.func,
    setSubtreeRoot: PropTypes.func.isRequired,
    setSelectedVisualizer: PropTypes.func.isRequired,
    onExpandCollapseRow: PropTypes.func,
    depiMethods: DepiMethodsType,
};

export default function ReviewTable({
    isReadOnly,
    showState,
    showStatus,
    showSummary,
    showReview,
    showUuid,
    data,
    expandedRows,
    height,
    onExpandCollapseRow,
    selectedNode,
    setSelectedNode,
    setSubtreeRoot,
    setSelectedVisualizer,
    depiMethods,
}) {
    const [pageSize, setPageSize] = useState(25);
    const [pageIndex, setPageIndex] = useState(0);
    const [searchTerm, setSearchTerm] = useState('');

    const filteredRows = searchTerm ? data.filter((row) => row.node.name.toLowerCase().includes(searchTerm)) : data;
    const paginatedRows = filteredRows.slice(pageIndex * pageSize, (pageIndex + 1) * pageSize);

    const depiAvailable = Boolean(depiMethods);

    const onViewNode = useCallback(
        (nodeId) => {
            setSelectedNode({ nodeId, treeId: null });
            setSubtreeRoot(nodeId);
            setSelectedVisualizer('default');
        },
        [setSubtreeRoot, setSelectedVisualizer, setSelectedNode]
    );

    return (
        <CommonTableHeadAndFoot
            isReadOnly={isReadOnly}
            rowCount={filteredRows.length}
            pageIndex={pageIndex}
            pageSize={pageSize}
            searchTerm={searchTerm}
            setSearchTerm={setSearchTerm}
            setPageIndex={setPageIndex}
            setPageSize={setPageSize}
        >
            <TableContainer style={{ maxHeight: height - 120 }} component={Paper}>
                <Table stickyHeader size={'small'}>
                    <TableHead>
                        <TableRow>
                            <TableCell>Name</TableCell>
                            {showUuid && <TableCell>UUID</TableCell>}
                            <TableCell>Labels</TableCell>
                            {showSummary ? <TableCell>Summary</TableCell> : null}
                            {showReview ? <TableCell>Review</TableCell> : null}
                            {showStatus ? <TableCell>Status</TableCell> : null}
                            {depiAvailable && showState ? <TableCell>State</TableCell> : null}
                            <TableCell>Actions</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {paginatedRows.map((row) => (
                            <ReviewTableRow
                                key={row.id}
                                isExpanded={expandedRows.includes(row.id)}
                                depiAvailable={depiAvailable}
                                showState={showState}
                                showStatus={showStatus}
                                showSummary={showSummary}
                                showReview={showReview}
                                showUuid={showUuid}
                                row={row}
                                selectedNode={selectedNode}
                                setSelectedNode={setSelectedNode}
                                onViewNode={onViewNode}
                                onExpandCollapseRow={onExpandCollapseRow}
                            />
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
        </CommonTableHeadAndFoot>
    );
}
