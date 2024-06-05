import PropTypes from 'prop-types';
// @mui
import { Typography } from '@mui/material';
import { COLORS } from '../theme';

HyperLink.propTypes = {
    value: PropTypes.string.isRequired,
    title: PropTypes.string,
    onClick: PropTypes.func.isRequired,
    sx: PropTypes.object,
};

export default function HyperLink({ value, title, onClick, sx={} }) {
    return (
        <Typography
            title={title}
            sx={{
                marginTop: '9px',
                cursor: 'pointer',
                color: COLORS.HYPER_LINK,
                '&:hover': {
                    backgroundColor: COLORS.HYPER_LINK_HOVER_BG,
                },
                ...sx
            }}
            variant="body2"
            onClick={onClick}
        >
            {value}
        </Typography>
    );
}
