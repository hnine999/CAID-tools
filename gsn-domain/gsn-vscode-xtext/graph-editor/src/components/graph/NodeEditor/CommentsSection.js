import PropTypes from 'prop-types';
import { useMemo, useState, useEffect } from 'react';
// @mui
import {
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Badge,
    Button,
    Card,
    CardActions,
    CardContent,
    Grid,
    TextField,
    Typography,
} from '@mui/material';
import { ArrowForwardIosSharp as ArrowForwardIosSharpIcon } from '@mui/icons-material';
// components
import WrapWithLabel from './WrapWithLabel';
// utils
import { fToNow } from '../formatTime';
import { NodeType, NodeCommentsType } from '../gsnTypes';
import { labelStyle } from '../FormComponents/common';

// ----------------------------------------------------------------------
const buttonStyle = { fontSize: '0.8rem', textTransform: 'none', fontWeight: '600' };
CommentsSection.propTypes = {
    nodeData: NodeType,
    isReadOnly: PropTypes.bool,
    nodeComments: NodeCommentsType,
    onAddNewComment: PropTypes.func.isRequired,
    onDeleteComment: PropTypes.func.isRequired,
};

export default function CommentsSection({ nodeData, nodeComments, isReadOnly, onAddNewComment, onDeleteComment }) {
    const [expanded, setExpanded] = useState(false);
    const [isAdding, setIsAdding] = useState(false);
    const [newCommentStr, setNewCommentStr] = useState('');

    useEffect(() => {
        setIsAdding(() => false);
    }, [nodeData.uuid]);

    const cards = useMemo(() => {
        if (nodeComments.length === 0 && !isAdding) {
            return [
                <Typography
                    key="none=added"
                    style={{ color: 'grey', fontStyle: 'italic', ...labelStyle }}
                    variant="body2"
                >
                    None added ..
                </Typography>,
            ];
        }

        const cards = nodeComments.map(({ comment, user, timestamp }, idx) => (
            <Card key={`${idx}`} variant="outlined">
                <CardContent sx={{ p: 1 }}>
                    <Typography title={user.email} sx={{ fontSize: 10 }} color="text.secondary" gutterBottom>
                        {user.name}
                    </Typography>
                    <Typography variant="body2">{comment}</Typography>
                </CardContent>
                <CardActions>
                    <Grid container justifyContent="space-between" alignItems="center">
                        <Grid item>
                            <Typography title={new Date(timestamp)} sx={{ fontSize: 10 }} color="text.secondary">
                                {fToNow(timestamp)}
                            </Typography>
                        </Grid>
                        <Grid item>
                            <Button
                                size="small"
                                onClick={() => {
                                    onDeleteComment(nodeData.uuid, timestamp);
                                }}
                            >
                                DELETE
                            </Button>
                        </Grid>
                    </Grid>
                </CardActions>
            </Card>
        ));

        if (isAdding) {
            cards.unshift(
                <Card key={`new-comment`} variant="outlined">
                    <CardContent sx={{ p: 1 }}>
                        <TextField
                            type="text"
                            placeholder="Enter new comment ..."
                            multiline
                            fullWidth
                            minRows={3}
                            value={newCommentStr}
                            onChange={(el) => {
                                setNewCommentStr(el.target.value);
                            }}
                        />
                    </CardContent>
                    <CardActions>
                        <Grid container justifyContent="space-between" alignItems="center">
                            <Grid item>
                                <Button
                                    size="small"
                                    onClick={() => {
                                        setIsAdding(false);
                                        setNewCommentStr('');
                                    }}
                                >
                                    CANCEL
                                </Button>
                            </Grid>
                            <Grid item>
                                <Button
                                    size="small"
                                    disabled={!newCommentStr}
                                    onClick={() => {
                                        onAddNewComment(nodeData.uuid, newCommentStr);
                                        setIsAdding(false);
                                        setNewCommentStr('');
                                    }}
                                >
                                    SAVE
                                </Button>
                            </Grid>
                        </Grid>
                    </CardActions>
                </Card>
            );
        }

        return cards;
    }, [nodeData, nodeComments, onDeleteComment, onAddNewComment, isAdding, newCommentStr]);

    return (
        <Grid container spacing={1} sx={{ marginTop: 0 }}>
            <Accordion
                sx={{ width: '100%' }}
                disableGutters
                elevation={0}
                square
                expanded={expanded}
                onChange={() => {
                    if (expanded && isAdding) {
                        return;
                    }
                    setExpanded(!expanded);
                }}
            >
                <AccordionSummary
                    sx={{
                        flexDirection: 'row-reverse',
                        '& .MuiAccordionSummary-expandIconWrapper.Mui-expanded': {
                            transform: 'rotate(90deg)',
                        },
                        '& .MuiAccordionSummary-content': {
                            marginLeft: 1,
                            marginBottom: 0,
                            marginTop: 0,
                        },
                    }}
                    expandIcon={<ArrowForwardIosSharpIcon sx={{ fontSize: '0.75rem', marginTop: '6px' }} />}
                >
                    <WrapWithLabel label={'Comments'} labelSx={{ marginTop: '10px' }}>
                        {!expanded && (
                            <Badge
                                sx={{
                                    '& .MuiBadge-badge': {
                                        left: -5,
                                        top: 8,
                                    },
                                }}
                                color="primary"
                                badgeContent={nodeComments.length}
                            />
                        )}
                    </WrapWithLabel>

                    <Button
                        disabled={isReadOnly || isAdding}
                        sx={buttonStyle}
                        title="Add new Comment"
                        onClick={(e) => {
                            if (expanded) {
                                e.stopPropagation();
                            }

                            setIsAdding(true);
                        }}
                    >
                        + ADD
                    </Button>
                </AccordionSummary>
                <AccordionDetails sx={{ margin: 0, paddingTop: 0, paddingBottom: 1 }}>{cards}</AccordionDetails>
            </Accordion>
        </Grid>
    );
}
