import PropTypes from 'prop-types';
import React from 'react';
// @mui
import { InputAdornment, Menu, MenuItem } from '@mui/material';
import { Menu as MenuIcon } from '@mui/icons-material';

CategorySelector.propTypes = {
    searchCategory: PropTypes.shape({
        id: PropTypes.string,
        displayName: PropTypes.string,
    }).isRequired,
    searchCategories: PropTypes.object.isRequired,
    setSearchCategory: PropTypes.func.isRequired,
};

export default function CategorySelector({ searchCategory, searchCategories, setSearchCategory }) {
    const [anchorEl, setAnchorEl] = React.useState(null);
    const open = Boolean(anchorEl);
    const handleClick = (event) => {
        setAnchorEl(event.currentTarget);
    };

    const handleSelect = (categoryId) => {
        setAnchorEl(null);
        setSearchCategory(searchCategories[categoryId]);
    };

    return (
        <InputAdornment position="end">
            <MenuIcon style={{ cursor: 'pointer' }} onClick={handleClick} />
            <Menu
                id="basic-menu"
                anchorEl={anchorEl}
                open={open}
                onClose={() => {
                    setAnchorEl(null);
                }}
                MenuListProps={{
                    'aria-labelledby': 'basic-button',
                }}
            >
                {Object.keys(searchCategories).map((categoryId) => (
                    <MenuItem
                        disabled={categoryId === searchCategory.id}
                        key={categoryId}
                        onClick={() => handleSelect(categoryId)}
                    >
                        {searchCategories[categoryId].displayName}
                    </MenuItem>
                ))}
            </Menu>
        </InputAdornment>
    );
}
