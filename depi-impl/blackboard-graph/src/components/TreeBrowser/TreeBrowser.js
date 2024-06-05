import PropTypes from 'prop-types';
import React, { useCallback, useMemo, useState } from 'react';
import { useDebounce } from 'use-debounce';
// @mui
import { InputAdornment, Grid, TextField } from '@mui/material';
import { Search as SearchIcon, Clear as ClearIcon } from '@mui/icons-material';
// components
import TreeBrowserView from './TreeBrowserView';
import CategorySelector from './CategorySelector';
// utils
import { expandResources } from '../BlackboardGraph/graphUtils';
import { getFullResourceGroupId, getFullResourceId } from '../../utils';
import { DepiModel } from '../../depiTypes';

// -----------------------------------------------------------------------------------------------

const SEARCH_CATEGORIES = {
    name: { id: 'name', displayName: 'Name' },
    url: { id: 'url', displayName: 'URL' },
};

TreeBrowser.propTypes = {
    depiModel: DepiModel,
    setSelection: PropTypes.func.isRequired,
    width: PropTypes.number.isRequired,
};

export default function TreeBrowser({ depiModel, setSelection, width }) {
    const [searchValue, setSearchValue] = useState('');
    const [searchString] = useDebounce(searchValue, 200);
    const [searchCategory, setSearchCategory] = useState(SEARCH_CATEGORIES.name);

    const [treeRoots, idToTreeNode] = useMemo(() => {
        const resourceGroups = new Map();
        const roots = [];
        const idToTreeNode = {};
        depiModel.resourceGroups.forEach((resourceGroup) => {
            const rgId = getFullResourceGroupId(resourceGroup);
            resourceGroups.set(rgId, resourceGroup);
            idToTreeNode[rgId] = {
                id: rgId,
                label: resourceGroup.name,
            };

            roots.push(idToTreeNode[rgId]);
        });

        expandResources(depiModel.resources, resourceGroups, ({ id, parentId, resource, name }) => {
            idToTreeNode[id] = {
                id,
                resource,
                label: name,
                hidden: !resource,
            };

            idToTreeNode[parentId].children = idToTreeNode[parentId].children || [];
            idToTreeNode[parentId].children.push(idToTreeNode[id]);
            idToTreeNode[id].parent = idToTreeNode[parentId];
        });

        return [roots, idToTreeNode];
    }, [depiModel]);

    const [expanded, setExpanded] = useState([]);

    const [searchRoots, hasFilter] = useMemo(() => {
        const matchedResourceIds = new Set();
        if (!searchString) {
            return [treeRoots, false];
        }

        const compareString = searchString.toLowerCase();

        depiModel.resources.forEach((resource) => {
            function compare(values) {
                // eslint-disable-next-line no-restricted-syntax
                for (const value of values) {
                    if (value.toLowerCase().includes(compareString)) {
                        return true;
                    }
                }

                return false;
            }

            let match = false;

            switch (searchCategory.id) {
                case SEARCH_CATEGORIES.name.id:
                    match = compare([resource.name]);
                    break;
                case SEARCH_CATEGORIES.url.id:
                    match = compare([resource.url]);
                    break;
                // case SEARCH_CATEGORIES.labels.id:
                //     match = compare(resource.labels || []);
                //     break;
                default:
                    match = false;
                    break;
            }

            if (match) {
                matchedResourceIds.add(getFullResourceId(resource));
            }
        });

        // Optimize corner cases.
        if (matchedResourceIds.size === 0) {
            return [[], false];
        }

        if (matchedResourceIds.size === depiModel.resources.length) {
            return [treeRoots, false];
        }

        // These exclude nodes that themselves aren't matches but are parents of matches.
        const displayedTreeNodeIds = new Set();

        treeRoots.forEach((root) => {
            function traverseRec(treeNode) {
                let isHidden = !matchedResourceIds.has(treeNode.id);

                (treeNode.children || []).forEach((childNode) => {
                    const childHidden = traverseRec(childNode);
                    isHidden = isHidden ? childHidden : isHidden;
                });

                if (!isHidden) {
                    displayedTreeNodeIds.add(treeNode.id);
                }

                return isHidden;
            }

            traverseRec(root);
        });

        const filteredRoots = [];
        treeRoots.forEach((root) => {
            function traverseRec(treeNode, newNode) {
                if (!matchedResourceIds.has(treeNode.id)) {
                    // It didn't match the search but has children -> keep it but "grey it out".
                    newNode.hidden = true;
                }

                (treeNode.children || []).forEach((childNode) => {
                    if (!displayedTreeNodeIds.has(childNode.id)) {
                        return;
                    }

                    if (!newNode.children) {
                        newNode.children = [];
                    }

                    const newChildNode = { ...childNode };
                    delete newChildNode.children;

                    newNode.children.push(newChildNode);

                    traverseRec(childNode, newChildNode);
                });
            }

            if (!displayedTreeNodeIds.has(root)) {
                const newRoot = { id: root.id, label: root.label };
                traverseRec(root, newRoot);
                if (newRoot.children) {
                    filteredRoots.push(newRoot);
                }
            }
        });

        return [filteredRoots, true];
    }, [searchString, depiModel, treeRoots, searchCategory]);

    const onTreeNodeClick = useCallback(
        (treeNodeId) => {
            const treeNode = idToTreeNode[treeNodeId];
            if (treeNode.resource) {
                setSelection([{ isLink: false, inDepi: true, onBlackboard: false, entry: treeNode.resource }]);
            }
        },
        [idToTreeNode, setSelection]
    );

    const onToggleExpandClick = useCallback(
        (treeNodeId) => {
            if (expanded.includes(treeNodeId)) {
                setExpanded(expanded.filter((id) => id !== treeNodeId));
            } else {
                setExpanded([...expanded, treeNodeId]);
            }
        },
        [expanded]
    );

    // const onSearchNodeClick = useCallback(
    //     (treeNodeId) => {
    //         // First expand all nodes up to the treeNode
    //         let treeNode = idToTreeNode[treeNodeId];
    //         const toExpand = [];

    //         while (treeNode && treeNode.parent) {
    //             treeNode = treeNode.parent;
    //             if (expanded.includes(treeNode.id)) {
    //                 break;
    //             }

    //             toExpand.push(treeNode.id);
    //         }

    //         setExpanded([...expanded, ...toExpand]);
    //         onTreeNodeClick(treeNodeId);
    //         setSearchValue('');
    //     },
    //     [onTreeNodeClick, expanded, idToTreeNode]
    // );

    return (
        <Grid container spacing={1} style={{ padding: 10 }}>
            <Grid item xs={12}>
                <TextField
                    size="small"
                    fullWidth
                    variant="outlined"
                    autoFocus
                    onKeyDown={(e) => {
                        if (e.key === 'Escape') {
                            setSearchValue('');
                        }
                    }}
                    value={searchValue}
                    label={searchCategory.displayName}
                    onChange={(event) => {
                        setSearchValue(event.target.value);
                    }}
                    InputProps={{
                        startAdornment: (
                            <InputAdornment position="start">
                                <SearchIcon />
                            </InputAdornment>
                        ),
                        endAdornment: searchValue ? (
                            <InputAdornment
                                position="end"
                                style={{ cursor: 'pointer' }}
                                onClick={() => {
                                    setSearchValue('');
                                }}
                            >
                                <ClearIcon />
                            </InputAdornment>
                        ) : (
                            <CategorySelector
                                searchCategories={SEARCH_CATEGORIES}
                                searchCategory={searchCategory}
                                setSearchCategory={setSearchCategory}
                            />
                        ),
                    }}
                />
            </Grid>

            <Grid item xs={12}>
                <TreeBrowserView
                    style={{ maxWidth: width }}
                    treeRoots={searchRoots}
                    expanded={hasFilter ? Object.keys(idToTreeNode) : expanded}
                    onNodeClick={onTreeNodeClick}
                    onNodeToggleExpand={onToggleExpandClick}
                    selectedIds={[]}
                />
            </Grid>
        </Grid>
    );
}
