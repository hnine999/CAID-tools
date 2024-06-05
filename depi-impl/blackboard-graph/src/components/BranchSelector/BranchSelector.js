import PropTypes from 'prop-types';
// @mui
import MultiSelectInput from './MultSelectInput';
// ----------------------------------------------------------------------

BranchSelector.propTypes = {
    branchName: PropTypes.string,
    branchesAndTags: PropTypes.shape({
        branches: PropTypes.arrayOf(PropTypes.string),
        tags: PropTypes.arrayOf(PropTypes.string),
    }),
    onSwitchBranch: PropTypes.func,
};

export default function BranchSelector({ branchesAndTags, branchName, onSwitchBranch }) {
    const options = branchesAndTags.branches.map((name) => ({ value: name, label: name }));
    return (
        <MultiSelectInput
            label="Branch"
            options={options}
            value={branchName}
            onSubmit={(branchName) => onSwitchBranch(branchName)}
        />
    );
}
