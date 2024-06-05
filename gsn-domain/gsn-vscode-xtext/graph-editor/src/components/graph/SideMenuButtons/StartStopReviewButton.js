import PropTypes from 'prop-types';
import { Badge, ListItem, ListItemButton, ListItemIcon } from '@mui/material';
import { RateReview as RateReviewIcon } from '@mui/icons-material';

StartStopReviewButton.propTypes = {
    onStartReview: PropTypes.func,
    onStopReview: PropTypes.func,
    reviewTag: PropTypes.string,
};

export default function StartStopReviewButton({ onStartReview, onStopReview, reviewTag }) {
    return (
        <ListItem key="start-review-button" disablePadding sx={{ display: 'block' }}>
            <ListItemButton
                sx={{
                    minHeight: 48,
                    justifyContent: 'center',
                    px: 2.5,
                }}
                onClick={reviewTag ? onStopReview : onStartReview}
                title={reviewTag ? 'Stop review ...' : 'Start review ...'}
            >
                <ListItemIcon
                    sx={{
                        minWidth: 0,
                        mr: 'auto',
                        justifyContent: 'center',
                    }}
                >
                    {reviewTag ? (
                        <Badge
                            color="success"
                            anchorOrigin={{
                                vertical: 'top',
                                horizontal: 'left',
                            }}
                            sx={{ transform: 'translate(10px, 0)' }}
                            badgeContent={'Review'}
                        >
                            <div style={{ transform: 'translate(-10px, 0)' }}>
                                <RateReviewIcon />
                            </div>
                        </Badge>
                    ) : (
                        <RateReviewIcon />
                    )}
                </ListItemIcon>
            </ListItemButton>
        </ListItem>
    );
}
