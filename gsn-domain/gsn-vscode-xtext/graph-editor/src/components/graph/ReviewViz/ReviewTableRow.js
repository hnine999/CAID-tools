import PropTypes from 'prop-types';
import React, { useMemo } from 'react';
// @mui
import { Box, Button, Collapse, TableCell, TableRow, Table, TableHead, TableBody } from '@mui/material';
// components
import { ChipListValues } from '../FormComponents';
// utils
import { COLORS } from '../theme';
import GSN_CONSTANTS from '../GSN_CONSTANTS';

const { NODE_STATUS_OPTIONS, NODE_DEPI_STATES } = GSN_CONSTANTS;

ReviewTableRow.propTypes = {
    depiAvailable: PropTypes.bool,
    showState: PropTypes.bool,
    showStatus: PropTypes.bool,
    showSummary: PropTypes.bool,
    showReview: PropTypes.bool,
    showUuid: PropTypes.bool,
    isExpanded: PropTypes.bool,
    row: PropTypes.shape({
        id: PropTypes.string,
        state: PropTypes.string,
        hasDirt: PropTypes.bool,
        hasNotReviewed: PropTypes.bool,
        reviewed: PropTypes.bool,
        solutions: PropTypes.array,
        node: PropTypes.shape({
            uuid: PropTypes.string,
            name: PropTypes.string,
            summary: PropTypes.string,
            labels: PropTypes.arrayOf(PropTypes.string),
            status: PropTypes.string,
        }),
    }).isRequired,
    selectedNode: PropTypes.oneOfType([
        PropTypes.shape({
            nodeId: PropTypes.string,
            treeId: PropTypes.string,
        }),
        PropTypes.arrayOf(PropTypes.string),
    ]),
    setSelectedNode: PropTypes.func.isRequired,
    onViewNode: PropTypes.func.isRequired,
    onExpandCollapseRow: PropTypes.func,
};

export default function ReviewTableRow({
    depiAvailable,
    isExpanded,
    showState,
    showStatus,
    showSummary,
    showReview,
    showUuid,
    row,
    selectedNode,
    setSelectedNode,
    onViewNode,
    onExpandCollapseRow,
}) {
    const selected = useMemo(() => selectedNode.nodeId === row.id, [selectedNode.nodeId, row.id]);
    const statusCell = useMemo(() => {
        if (!showStatus) {
            return null;
        }
        const status = row.node.status || NODE_STATUS_OPTIONS.NOT_REVIEWED;
        let color = 'grey';
        switch (status) {
            case NODE_STATUS_OPTIONS.APPROVED:
                color = COLORS.STATUS.APPROVED;
                break;
            case NODE_STATUS_OPTIONS.DISAPPROVED:
                color = COLORS.STATUS.DISAPPROVED;
                break;
            default:
                break;
        }

        return <TableCell style={{ color }}>{status}</TableCell>;
    }, [row.node.status, showStatus]);

    const reviewedCell = useMemo(() => {
        if (!showReview) {
            return null;
        }

        let reviewStatus = row.reviewed ? 'Reviewed' : 'Ready for Review';
        if (row.reviewed) {
            if (row.hasDirt) {
                reviewStatus += ' but dirty evidence';
            }

            if (row.hasNotReviewed) {
                reviewStatus += ` ${row.hasDirt ? 'and' : 'but'} unreviewed sub-goals`;
            }
        } else {
            if (row.hasDirt) {
                reviewStatus = 'Clean up evidence';
            }

            if (row.hasNotReviewed) {
                reviewStatus += `${row.hasDirt ? ' and review' : 'Review'} sub-goals`;
            }
        }

        return <TableCell>{reviewStatus}</TableCell>;
    }, [showReview, row.hasDirt, row.reviewed, row.hasNotReviewed]);

    const stateCell = useMemo(() => {
        if (!(depiAvailable && showState)) {
            return null;
        }

        let color = 'grey';
        switch (row.state) {
            case NODE_DEPI_STATES.RESOURCE_UP_TO_DATE:
                color = COLORS.STATUS.APPROVED;
                break;
            case NODE_DEPI_STATES.RESOURCE_DIRTY:
                color = 'brown';
                break;

            case NODE_DEPI_STATES.LOADING:
            case NODE_DEPI_STATES.NO_LINKED_EVIDENCE:
            case NODE_DEPI_STATES.NO_DEPI_RESOURCE:
            default:
                break;
        }

        return <TableCell style={{ color }}>{row.state}</TableCell>;
    }, [depiAvailable, row.state, showState]);

    return (
        <>
            <TableRow key={row.id} style={{ backgroundColor: selected ? COLORS.SELECTED(false) : undefined }}>
                <TableCell>{row.node.name}</TableCell>
                {showUuid && <TableCell>{row.node.uuid}</TableCell>}
                <TableCell>
                    <ChipListValues isReadOnly values={row.node.labels} noValuesMessage="No labels .." />
                </TableCell>
                {showSummary ? (
                    <TableCell style={{ width: 300, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {row.node.summary}
                    </TableCell>
                ) : null}
                {reviewedCell}
                {statusCell}
                {stateCell}
                <TableCell>
                    <Button onClick={() => onViewNode(row.id)}>VIEW</Button>
                    <Button onClick={() => setSelectedNode({ nodeId: row.id, treeId: null })}>SELECT</Button>
                    {onExpandCollapseRow && (
                        <Button onClick={() => onExpandCollapseRow(row.id)}>
                            {isExpanded ? 'HIDE SOLUTIONS' : 'LIST SOLUTIONS'}
                        </Button>
                    )}
                </TableCell>
            </TableRow>
            {onExpandCollapseRow && (
                <TableRow>
                    <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={6}>
                        <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                            <Box sx={{ margin: 1 }}>
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Name</TableCell>
                                            {showUuid && <TableCell>UUID</TableCell>}
                                            <TableCell>Labels</TableCell>
                                            {depiAvailable && <TableCell>State</TableCell>}
                                            <TableCell>Actions</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {row.solutions.map((solRow) => (
                                            <ReviewTableRow
                                                key={solRow.id}
                                                isExpanded={false}
                                                depiAvailable={depiAvailable}
                                                showState
                                                showStatus={false}
                                                showSummary={false}
                                                showReview={false}
                                                showUuid={showUuid}
                                                row={solRow}
                                                selectedNode={selectedNode}
                                                setSelectedNode={setSelectedNode}
                                                onViewNode={onViewNode}
                                            />
                                        ))}
                                    </TableBody>
                                </Table>
                            </Box>
                        </Collapse>
                    </TableCell>
                </TableRow>
            )}
        </>
    );
}
