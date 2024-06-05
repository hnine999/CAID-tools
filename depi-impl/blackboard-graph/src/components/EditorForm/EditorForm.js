/* eslint-disable react/jsx-no-bind */
import React from 'react';
import PropTypes from 'prop-types';
// components
import ResourceAndLinkForm from './ResourceAndLinkForm';
// utils
import { SelectionEntry } from '../../depiTypes';
import ResourceGroupForm from './ResourceGroupForm';

// ----------------------------------------------------------------------
EditorForm.propTypes = {
    isBlackboardEmpty: PropTypes.bool,
    isReadOnly: PropTypes.bool,
    selection: PropTypes.arrayOf(SelectionEntry).isRequired,
    // Actions
    onRevealInEditor: PropTypes.func.isRequired,
    onViewResourceDiff: PropTypes.func.isRequired,
    onRemoveEntriesFromBlackboard: PropTypes.func.isRequired,
    onDeleteEntriesFromDepi: PropTypes.func.isRequired,
    onMarkLinksClean: PropTypes.func.isRequired,
    onMarkInferredDirtinessClean: PropTypes.func.isRequired,
    onMarkAllClean: PropTypes.func.isRequired,
    onShowDependencyGraph: PropTypes.func.isRequired,
    onEditResourceGroup: PropTypes.func.isRequired,
};

export default function EditorForm({ selection, ...rest }) {
    const selectedResourceGroup = selection.find((s) => s.isResourceGroup);
    return selectedResourceGroup ? (
        <ResourceGroupForm resourceGroup={selectedResourceGroup.entry} {...rest} />
    ) : (
        <ResourceAndLinkForm selection={selection} {...rest} />
    );
}
