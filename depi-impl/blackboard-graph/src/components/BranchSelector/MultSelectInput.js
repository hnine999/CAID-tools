import PropTypes from 'prop-types';
// @mui
import { FormControl, InputLabel, MenuItem, Select } from '@mui/material';
import { COLORS } from '../../theme';
// ----------------------------------------------------------------------

MultiSelectInput.propTypes = {
    isReadOnly: PropTypes.bool,
    label: PropTypes.string,
    value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    options: PropTypes.arrayOf(
        PropTypes.shape({
            label: PropTypes.string,
            value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
        })
    ).isRequired,
    onSubmit: PropTypes.func.isRequired,
};

export default function MultiSelectInput({ isReadOnly, label, value, options, onSubmit }) {
    return (
        <FormControl
            sx={{
                minWidth: 120,
                marginTop: 0,
                '& .MuiInputLabel-root': {
                    color: COLORS.LIGHT_GREY,
                },
                '& .MuiInputBase-root': {
                    color: COLORS.LIGHT_GREY,
                },
                '& .MuiOutlinedInput-notchedOutline': {
                    borderColor: COLORS.LIGHT_GREY,
                },
                '& .MuiSelect-iconOutlined': {
                    color: COLORS.LIGHT_GREY,
                },
            }}
            disabled={isReadOnly}
            size="small"
        >
            <InputLabel>{label}</InputLabel>
            <Select label={label} value={value} onChange={(event) => onSubmit(event.target.value)}>
                {options.map((info) => (
                    <MenuItem key={info.value} value={info.value}>
                        {info.label}
                    </MenuItem>
                ))}
            </Select>
        </FormControl>
    );
}
