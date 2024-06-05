/* eslint-disable react/jsx-no-bind */
import React from 'react';
import PropTypes from 'prop-types';
// @mui
import { IconButton, Grid, TextField, Typography } from '@mui/material';
import {
    DeleteOutline as DeleteOutlineIcon,
    ZoomInMap as ZoomInMapIcon,
    OpenInNew as OpenInNewIcon,
} from '@mui/icons-material';
// components
import WrapWithLabel from './WrapWithLabel';
import GSNIcons, { Goal, SolvedBy } from '../icons';
// utils
import GSN_CONSTANTS from '../GSN_CONSTANTS';
import { isReference } from '../ChangeConfirmation/getDeleteImplications';
import modelUtils from '../modelUtils';

// ----------------------------------------------------------------------

const { SOLUTION } = GSN_CONSTANTS.TYPES;

IconHeader.propTypes = {
    nodeData: PropTypes.shape({
        id: PropTypes.string.isRequired,
        type: PropTypes.string.isRequired,
        name: PropTypes.string.isRequired,
        uuid: PropTypes.string,
        srcId: PropTypes.string,
        dstId: PropTypes.string,
    }),
    isReadOnly: PropTypes.bool,
    reviewTag: PropTypes.string,
    onDeleteNode: PropTypes.func,
    onDeleteConnection: PropTypes.func,
    setSubtreeRoot: PropTypes.func,
    onRevealOrigin: PropTypes.func,
};

const actionBtnStyle = (isRhs, idx) => ({
    position: 'absolute',
    top: 16 + 36 * idx,
    left: isRhs ? undefined : 10,
    right: isRhs ? 10 : undefined,
});

export default function IconHeader({
    nodeData,
    isReadOnly,
    reviewTag,
    onDeleteNode,
    onDeleteConnection,
    setSubtreeRoot,
    onRevealOrigin,
}) {
    const { id, uuid, type, name, srcId, dstId } = nodeData;
    // Optional feature depending on implementation.
    const showRevealOriginBtn = typeof onRevealOrigin === 'function';
    const showSubtreeRootBtn = typeof setSubtreeRoot === 'function';
    let isRef = false;
    if (srcId && dstId) {
        const connInfo = modelUtils.tryParseModelIdOfConn(id);
        isRef = connInfo && isReference(connInfo.srcId, connInfo.dstId);
    }

    return (
        <Grid container spacing={2} style={{ padding: 10 }}>
            {reviewTag && (
                <Grid item xs={12} sx={{ alignItems: 'center', display: 'flex', justifyContent: 'center' }}>
                    <Typography variant="h5" component="div">
                        In review {reviewTag}
                    </Typography>
                </Grid>
            )}
            <Grid item xs={12} style={{ position: 'relative', textAlign: 'center' }}>
                {showSubtreeRootBtn ? (
                    <IconButton
                        title="Subtree view"
                        style={actionBtnStyle(false, 0)}
                        onClick={() => {
                            setSubtreeRoot(id);
                        }}
                    >
                        <ZoomInMapIcon />
                    </IconButton>
                ) : null}
                {showRevealOriginBtn ? (
                    <IconButton
                        title="Reveal node in .gsn files"
                        style={actionBtnStyle(false, 1)}
                        onClick={() => {
                            onRevealOrigin(id);
                        }}
                    >
                        <OpenInNewIcon />
                    </IconButton>
                ) : null}
                {srcId && dstId
                    ? React.createElement(GSNIcons[type] || SolvedBy, {
                          style: { margin: 'auto', height: 100 },
                          isRef,
                      })
                    : React.createElement(GSNIcons[type] || Goal, { style: { margin: 'auto', height: 100 } })}

                <Typography
                    style={{
                        position: 'absolute',
                        top: '50%',
                        left: '52%',
                        transform: 'translate(-50%, -50%)',
                        fontWeight: 'bold',
                        wordWrap: 'break-word',
                        width: [SOLUTION].includes(type) ? '95px' : '120px',
                    }}
                    variant="subtitle2"
                >
                    {name}
                </Typography>
                {isReadOnly ? null : (
                    <IconButton
                        title="Delete node"
                        aria-label="delete"
                        style={actionBtnStyle(true, 0)}
                        onClick={() => {
                            if (onDeleteNode) {
                                onDeleteNode(id, type);
                            } else if (onDeleteConnection && srcId && dstId) {
                                onDeleteConnection(srcId, type, dstId);
                            }
                        }}
                    >
                        <DeleteOutlineIcon />
                    </IconButton>
                )}
            </Grid>

            <WrapWithLabel label={'Type'}>
                <TextField
                    fullWidth
                    inputProps={{ style: { fontSize: 14 } }}
                    variant="standard"
                    type="text"
                    disabled
                    value={type}
                />
            </WrapWithLabel>

            {uuid ? (
                <WrapWithLabel label={'UUID'}>
                    <TextField
                        fullWidth
                        inputProps={{ style: { fontSize: 14 } }}
                        variant="standard"
                        type="text"
                        disabled
                        value={uuid}
                    />
                </WrapWithLabel>
            ) : null}

            <WrapWithLabel label={'ID'}>
                <TextField
                    fullWidth
                    inputProps={{ style: { fontSize: 14 } }}
                    variant="standard"
                    type="text"
                    disabled
                    value={id}
                />
            </WrapWithLabel>
        </Grid>
    );
}
