import PropTypes from 'prop-types';
// @mui
import { Grid, Typography } from '@mui/material';
// utils
import { labelStyle } from '../FormComponents/common';

WrapWithLabel.propTypes = {
    label: PropTypes.string,
    children: PropTypes.oneOfType([PropTypes.element, PropTypes.array]),
    labelSx: PropTypes.object,
};

export default function WrapWithLabel({ label, children, labelSx }) {
    return (
        <>
            <Grid item xs={3}>
                <Typography sx={{ ...labelStyle, ...labelSx }} variant="subtitle2">
                    {label}
                </Typography>
            </Grid>
            <Grid item xs={9}>
                {children}
            </Grid>
        </>
    );
}
