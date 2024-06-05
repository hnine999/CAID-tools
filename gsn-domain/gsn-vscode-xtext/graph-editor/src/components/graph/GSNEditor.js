import PropTypes from 'prop-types';
import { useState, useMemo, useCallback, useEffect } from 'react';
// @mui
import { Button } from '@mui/material';
import { EditNote as EditNoteIcon, Search as SearchIcon, TextSnippet as TextSnippetIcon } from '@mui/icons-material';
// components
import GSNGraph from './GSNGraph/GSNGraph';
import SideMenu from './SideMenu';
import NodeEditor from './NodeEditor';
import TreeBrowser from './TreeBrowser';
import DetailsEditor from './DetailsEditor';
import TopMenu from './TopMenu';
import VisualizerSelector from './VisualizerSelector';
import DefaultSideMenuBottomActions from './DefaultSideMenuBottomActions';
// utils
import modelUtils from './modelUtils';
import { applyViewToModel } from './TopMenu/ViewEditor/viewUtils';
import UserPreferences from './contexts/UserPreferences';
import {
    LabelType,
    NodeType,
    ViewType,
    LayoutOptsType,
    DepiMethodsType,
    NodeCommentsType,
    ResourceStateType,
} from './gsnTypes';
import GSN_CONSTANTS from './GSN_CONSTANTS';

// -----------------------------------------------------------------------------------------------

GSNEditor.propTypes = {
    model: PropTypes.arrayOf(NodeType).isRequired,
    views: PropTypes.arrayOf(ViewType).isRequired,
    labels: PropTypes.arrayOf(LabelType).isRequired,
    comments: PropTypes.objectOf(NodeCommentsType),
    depiResources: PropTypes.objectOf(ResourceStateType),
    width: PropTypes.number,
    height: PropTypes.number,
    layoutOpts: LayoutOptsType,
    userPreferences: PropTypes.shape({
        enforceUniqueNames: PropTypes.bool,
    }),
    isReadOnly: PropTypes.bool,
    reviewTag: PropTypes.string,
    selectedNode: PropTypes.shape({
        nodeId: PropTypes.string,
        treeId: PropTypes.string,
    }),
    extraSideMenuBottomActionEls: PropTypes.arrayOf(PropTypes.element),
    setSelectedNode: PropTypes.func.isRequired,
    onAttributeChange: PropTypes.func.isRequired,
    onNewChildNode: PropTypes.func.isRequired,
    onDeleteConnection: PropTypes.func.isRequired,
    onDeleteNode: PropTypes.func.isRequired,
    onAddNewView: PropTypes.func.isRequired,
    onDeleteView: PropTypes.func.isRequired,
    onRenameView: PropTypes.func.isRequired,
    onAddNewLabel: PropTypes.func.isRequired,
    onDeleteLabel: PropTypes.func.isRequired,
    onUpdateLabel: PropTypes.func.isRequired,
    onAddNewComment: PropTypes.func.isRequired,
    onDeleteComment: PropTypes.func.isRequired,
    onRevealOrigin: PropTypes.func,
    depiMethods: DepiMethodsType,
};

export default function GSNEditor({
    model,
    layoutOpts = {
        headerHeight: 0,
        leftMenuPanel: false,
        sideMenuWidth: 48,
        topMenuHeight: 28,
        defaultSideMenuItemWidth: 320,
        defaultTopMenuItemHeight: 360,
    },
    userPreferences = { enforceUniqueNames: false },
    views,
    extraSideMenuBottomActionEls = [],
    labels,
    comments,
    depiResources,
    width,
    height,
    isReadOnly,
    reviewTag,
    selectedNode,
    setSelectedNode,
    onAddNewView,
    onDeleteView,
    onRenameView,
    onAddNewLabel,
    onDeleteLabel,
    onUpdateLabel,
    onAddNewComment,
    onDeleteComment,
    depiMethods,
    ...editCallbacks
}) {
    const [subtreeRoot, setSubtreeRoot] = useState(null);
    const [activeView, setActiveView] = useState(null);
    const [doValidate, setDoValidate] = useState(false);
    const [selectedVisualizer, setSelectedVisualizer] = useState('default'); // 'table'
    const [sideMenuIndex, setSideMenuIndex] = useState(0);
    const [topMenuIndex, setTopMenuIndex] = useState(-1);
    // eslint-disable-next-line no-unused-vars
    const [menuItemWidth, setMenuItemWidth] = useState(layoutOpts.defaultSideMenuItemWidth);

    const centerPanelWidth = width - layoutOpts.sideMenuWidth - menuItemWidth;

    useEffect(() => {
        const handleKeyDown = (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                setSelectedNode({ nodeId: null, treeId: null });
                e.preventDefault();
            }
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);

        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Get filtered out model and filter info.
    const { graphData, filter } = useMemo(() => {
        if (activeView === null) {
            if (subtreeRoot === null) {
                return { graphData: model, filter: null };
            }
        }

        let subModel = model;
        const idToNode = modelUtils.getIdToNodeMap(model);

        let filter = null;

        if (activeView && activeView.expression) {
            subModel = applyViewToModel(model, labels, activeView, idToNode);
            filter = {
                expandAll: activeView.expandAll,
            };

            if (activeView.highlightMatches) {
                const idsInView = new Set();

                filter.highlighted = {};
                subModel.forEach((node) => {
                    idsInView.add(node.id);
                });

                model.forEach((node) => {
                    if (idsInView.has(node.id)) {
                        filter.highlighted[node.id] = {};
                    } else {
                        filter.highlighted[node.id] = { hidden: true };
                    }
                });
                subModel = model;
            }
        }

        if (subtreeRoot && idToNode[subtreeRoot]) {
            const { children } = modelUtils.getChildIds(subModel, subtreeRoot, idToNode, true);
            const { parents } = modelUtils.getParentIds(subModel, subtreeRoot, idToNode);

            subModel = subModel.filter((n) => n.id === subtreeRoot || children[n.id] || parents[n.id]);
        }

        return { graphData: subModel, filter };
    }, [subtreeRoot, activeView, model, labels]);

    // Add validation information to filter (if active).
    const augmentedFilter = useMemo(() => {
        if (!doValidate) {
            return filter;
        }

        let newFilter;
        if (filter) {
            // TODO: Avoid this parse/stringify
            newFilter = JSON.parse(JSON.stringify(filter));
            newFilter.highlighted = newFilter.highlighted || {};
        } else {
            newFilter = { highlighted: {} };
        }

        const { highlighted } = newFilter;

        graphData.forEach((node) => {
            if (node.type === GSN_CONSTANTS.TYPES.GOAL || node.type === GSN_CONSTANTS.TYPES.SOLUTION) {
                highlighted[node.id] = highlighted[node.id] || {};
                highlighted[node.id].highlight = 2; // NOT_REVIEWED (default)

                if (node.status === GSN_CONSTANTS.NODE_STATUS_OPTIONS.APPROVED) {
                    highlighted[node.id].highlight = 1;
                } else if (node.status === GSN_CONSTANTS.NODE_STATUS_OPTIONS.DISAPPROVED) {
                    highlighted[node.id].highlight = 3;
                }
            }
            // else if (node.type === GSN_CONSTANTS.TYPES.SOLUTION) {
            //     highlighted[node.id] = highlighted[node.id] || {};
            //     highlighted[node.id].highlight = 2; // NO_LINKED_EVIDENCE (default)
            //     console.log(depiResources && depiResources[node.uuid]);
            //     if (depiResources && depiResources[node.uuid]) {
            //         const status = depiResources[node.uuid];
            //         if (status === GSN_CONSTANTS.NODE_DEPI_STATES.RESOURCE_UP_TO_DATE) {
            //             highlighted[node.id].highlight = 1;
            //         } else if (status === GSN_CONSTANTS.NODE_DEPI_STATES.RESOURCE_DIRTY) {
            //             highlighted[node.id].highlight = 3;
            //         }
            //     }
            // }
        });

        // const nodeIdMap = {};
        // const subtreeRoots = [];

        // graphData.forEach((node) => {
        //     nodeIdMap[node.id] = node;
        //     if (node.type === GSN_CONSTANTS.TYPES.SOLUTION) {
        //         highlighted[node.id] = highlighted[node.id] || {};
        //         highlighted[node.id].highlight = 2; // NOT_REVIEWED (default)

        //         if (node.status === GSN_CONSTANTS.NODE_STATUS_OPTIONS.APPROVED) {
        //             highlighted[node.id].highlight = 1;
        //         } else if (node.status === GSN_CONSTANTS.NODE_STATUS_OPTIONS.DISAPPROVED) {
        //             highlighted[node.id].highlight = 3;
        //         }
        //     } else if (GSN_CONSTANTS.SOLVED_BY_OWNERS.includes(node.type)) {
        //         subtreeRoots.push(node);
        //     }
        // });

        // // 1 - ok, 2 - unknown, 3 - false
        // // eslint-disable-next-line no-inner-declarations
        // function checkValidityRec(node) {
        //     highlighted[node.id] = highlighted[node.id] || {};
        //     // It's has been computed - return
        //     if (typeof highlighted[node.id].highlight === 'number') {
        //         return highlighted[node.id].highlight;
        //     }

        //     let value = 0;
        //     (node[GSN_CONSTANTS.RELATION_TYPES.SOLVED_BY] || []).forEach((childId) => {
        //         const childNode = nodeIdMap[childId];
        //         if (!childNode) {
        //             // Filtered out
        //             return;
        //         }

        //         const childValue = checkValidityRec(childNode);
        //         // Change this logic here when choices are available.
        //         value = childValue > value ? childValue : value;
        //     });

        //     // TODO: Should this be unknown or ok?
        //     highlighted[node.id].highlight = value === 0 ? 2 : value;

        //     return highlighted[node.id].highlight;
        // }

        // subtreeRoots.forEach(checkValidityRec);

        return newFilter;
    }, [filter, graphData, doValidate]);

    const defaultSideMenuBottomActions = useMemo(
        () => DefaultSideMenuBottomActions({ doValidate, setDoValidate }),
        [doValidate]
    );

    const sideMenuBottomActionsEls = useMemo(
        () => [...extraSideMenuBottomActionEls, ...defaultSideMenuBottomActions],
        [extraSideMenuBottomActionEls, defaultSideMenuBottomActions]
    );

    const exitSubtreeView = useCallback(() => {
        setSubtreeRoot(null);
    }, []);

    const onWidthChange = useCallback((w) => {
        setMenuItemWidth(w);
    }, []);

    const tryConnectNodes = useCallback(
        (nodeId, targetId) => {
            const result = modelUtils.isValidTarget(model, nodeId, targetId);
            if (!result.isValid) {
                // TODO: Consider doing something more stylish here..
                console.error(result.message);
                return;
            }

            editCallbacks.onNewChildNode(nodeId, result.relationType, null, targetId);
        },
        [model, editCallbacks]
    );

    useEffect(() => {
        if (sideMenuIndex > 0) {
            setSideMenuIndex(0);
        }

        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedNode.nodeId]);

    const menuItems = useMemo(() => {
        const menuItems = [];
        const { nodeId } = selectedNode;

        if (nodeId) {
            menuItems.push({
                icon: <EditNoteIcon />,
                title: 'View/edit fields',
                content: (
                    <NodeEditor
                        isReadOnly={isReadOnly}
                        reviewTag={reviewTag}
                        model={model}
                        labels={labels}
                        comments={comments}
                        depiResources={depiResources}
                        selectedNode={selectedNode}
                        setSelectedNode={setSelectedNode}
                        setSubtreeRoot={setSubtreeRoot}
                        setSideMenuIndex={setSideMenuIndex}
                        setTopMenuIndex={setTopMenuIndex}
                        depiMethods={depiMethods}
                        onAddNewComment={onAddNewComment}
                        onDeleteComment={onDeleteComment}
                        {...editCallbacks}
                    />
                ),
            });

            menuItems.push({
                icon: <TextSnippetIcon />,
                title: 'View/edit info',
                content: (
                    <DetailsEditor
                        width={menuItemWidth}
                        isReadOnly={isReadOnly || Boolean(reviewTag)}
                        model={model}
                        selectedNode={selectedNode}
                        onAttributeChange={editCallbacks.onAttributeChange}
                    />
                ),
            });
        } else {
            menuItems.push({
                icon: <SearchIcon />,
                title: 'Treebrowser',
                content: (
                    <TreeBrowser
                        width={menuItemWidth}
                        data={graphData}
                        selectedNode={selectedNode}
                        setSelectedNode={setSelectedNode}
                    />
                ),
            });
        }

        return menuItems;
    }, [
        isReadOnly,
        model,
        graphData,
        labels,
        comments,
        selectedNode,
        setSelectedNode,
        setSubtreeRoot,
        editCallbacks,
        menuItemWidth,
        depiMethods,
        reviewTag,
        onAddNewComment,
        onDeleteComment,
        depiResources,
    ]);

    const centerPanelLeft = layoutOpts.leftMenuPanel ? menuItemWidth + layoutOpts.sideMenuWidth : 0;
    const centerPanelRight = layoutOpts.leftMenuPanel ? 0 : layoutOpts.sideMenuWidth + menuItemWidth;

    return (
        <UserPreferences.Provider value={userPreferences}>
            {subtreeRoot ? (
                <Button
                    variant="outlined"
                    style={centerFloatingButtonStyle(true, centerPanelWidth, centerPanelLeft)}
                    onClick={exitSubtreeView}
                >
                    EXIT SUBTREE VIEW
                </Button>
            ) : null}
            <TopMenu
                left={centerPanelLeft}
                width={centerPanelWidth}
                totalHeight={height}
                layoutOpts={layoutOpts}
                isReadOnly={isReadOnly}
                labels={labels}
                views={views}
                model={model}
                activeView={activeView}
                topMenuIndex={topMenuIndex}
                setTopMenuIndex={setTopMenuIndex}
                setActiveView={setActiveView}
                onAddNewView={onAddNewView}
                onDeleteView={onDeleteView}
                onRenameView={onRenameView}
                onAddNewLabel={onAddNewLabel}
                onDeleteLabel={onDeleteLabel}
                onUpdateLabel={onUpdateLabel}
            />
            <GSNGraph
                selectedVisualizer={selectedVisualizer}
                data={graphData}
                model={model}
                depiResources={depiResources}
                filter={augmentedFilter}
                width={centerPanelWidth}
                left={centerPanelLeft}
                reviewTag={reviewTag}
                top={36}
                height={height - 36}
                minZoom={0.35}
                selectedNode={selectedNode}
                setSelectedNode={setSelectedNode}
                setSubtreeRoot={setSubtreeRoot}
                setSelectedVisualizer={setSelectedVisualizer}
                onConnectNodes={tryConnectNodes}
                depiMethods={depiMethods}
            />
            <SideMenu
                layoutOpts={layoutOpts}
                menuItems={menuItems}
                bottomActionEls={sideMenuBottomActionsEls}
                left={centerPanelLeft}
                totalWidth={width}
                sideMenuIndex={menuItems.length > sideMenuIndex ? sideMenuIndex : 0} // Saftey during node selected switch..
                onWidthChange={onWidthChange}
                setSideMenuIndex={setSideMenuIndex}
            />
            <VisualizerSelector
                right={centerPanelRight}
                selectedVisualizer={selectedVisualizer}
                setSelectedVisualizer={setSelectedVisualizer}
            />
        </UserPreferences.Provider>
    );
}

const centerFloatingButtonStyle = (isTop, width, left) => {
    let res = {
        position: 'absolute',
        left: (width - 140) / 2 + left,
        height: 26,
        zIndex: 1250,
    };

    if (isTop) {
        res = { ...res, top: 0, borderTopRightRadius: 0, borderTopLeftRadius: 0, borderTop: 'none' };
    } else {
        res = { ...res, bottom: 0, borderBottomRightRadius: 0, borderBottomLeftRadius: 0, borderBottom: 'none' };
    }

    return res;
};
