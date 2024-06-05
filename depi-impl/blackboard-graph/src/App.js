/* eslint-disable no-restricted-syntax */
/* globals acquireVsCodeApi */
import { useState, useEffect, useCallback, useMemo } from 'react';
import PropTypes from 'prop-types';
// @mui
import { Notes as NotesIcon, Search as SearchIcon } from '@mui/icons-material';
// components
import BlackboardGraph from './components/BlackboardGraph';
import AppBarHeader from './components/AppBarHeader';
import SideMenu from './components/SideMenu';
import EditorForm from './components/EditorForm';
import TreeBrowser from './components/TreeBrowser';
// utils
import DepiApi from './depi-api/DepiApi';
import { EVENT_TYPES } from './EVENT_TYPES';
import {
    isSameLink,
    isSameResource,
    getResourceRefFromResource,
    getAdditionalLooseLinks,
    getUpdatedSelection,
} from './utils';
import { Resource, LayoutOptsType } from './depiTypes';
import DependencyGraph from './components/DependencyGraph';

const vscode = typeof acquireVsCodeApi === 'function' ? acquireVsCodeApi() : null;
let depi = null;

App.propTypes = {
    isReadOnly: PropTypes.bool,
    startBranchName: PropTypes.string.isRequired,
    startResource: PropTypes.shape({ resource: Resource, dependants: PropTypes.bool }),
    layoutOpts: LayoutOptsType,
};

export default function App({
    isReadOnly,
    startBranchName,
    startResource,
    layoutOpts = { headerHeight: 64, leftMenuPanel: false, sideMenuWidth: 48, defaultSideMenuItemWidth: 320 },
}) {
    const [size, setSize] = useState({ height: 0, width: 0 });
    const [depiModel, setDepiModel] = useState({ resourceGroups: [], resources: [], links: [] });
    const [blackboardModel, setBlackboardModel] = useState({ resources: [], links: [] });
    const [dependencyGraph, setDependencyGraph] = useState({ resource: null, links: [], dependants: false });
    const [toolsConfig, setToolsConfig] = useState({});
    const [selection, setSelection] = useState([]);
    const [showDirtyness, setShowDirtyness] = useState(false);
    const [errorMessage, setErrorMessage] = useState(null);
    const darkMode = false;
    const [sideMenuIndex, setSideMenuIndex] = useState(-1);
    const [menuItemWidth, setMenuItemWidth] = useState(0);
    const [branchName] = useState(startBranchName);
    const [branchesAndTags, setBranchesAndTags] = useState({ branches: [], tags: [] });

    let centerPanelWidth = size.width - layoutOpts.sideMenuWidth - menuItemWidth;
    if (centerPanelWidth < 0) {
        centerPanelWidth = 0;
    }

    useEffect(() => {
        function handleResize() {
            const { innerWidth, innerHeight } = window;
            setSize({ width: innerWidth, height: innerHeight });
        }

        function depiEventHandler(data) {
            switch (data.type) {
                case EVENT_TYPES.TOOLS_CONFIG:
                    setToolsConfig(data.value);
                    break;
                case EVENT_TYPES.DEPI_MODEL:
                    setDepiModel(data.value);
                    break;
                case EVENT_TYPES.BLACKBOARD_MODEL:
                    setBlackboardModel(data.value);
                    break;
                case EVENT_TYPES.DEPENDENCY_GRAPH:
                    setDependencyGraph(data.value);
                    break;
                case EVENT_TYPES.BRANCHES_AND_TAGS:
                    setBranchesAndTags(data.value);
                    break;
                case EVENT_TYPES.ERROR_MESSAGE:
                    setErrorMessage(data.value);
                    break;
                default:
                    console.error(`UKNOWN event ${data}`);
            }
        }

        window.addEventListener('resize', handleResize);
        depi = new DepiApi(vscode, depiEventHandler);

        // Invocations at at start-up:
        handleResize();
        depi.requestToolsConfig();
        depi.requestBranchesAndTags();
        if (startResource) {
            // console.log('startResource defined', JSON.stringify(startResource));
            depi.requestDependencyGraph(startResource.resource, startBranchName, startResource.dependants);
        } else {
            depi.requestDepiModel(startBranchName);
            depi.requestBlackboard();
        }

        return () => {
            window.removeEventListener('resize', handleResize);
        };
    }, [startResource, startBranchName]);

    useEffect(() => {
        setSelection(getUpdatedSelection(selection, dependencyGraph, depiModel, blackboardModel));

        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [depiModel, blackboardModel, dependencyGraph]);

    const onExpandResourceGroups = useCallback((resourceGroupRefs) => {
        depi.expandResourceGroups(resourceGroupRefs);
    }, []);

    const onCollapseResourceGroups = useCallback((resourceGroupRefs) => {
        depi.collapseResourceGroups(resourceGroupRefs);
    }, []);

    const onLinkResources = useCallback((source, target) => {
        depi.linkResources(source, target);
    }, []);

    const onSaveBlackboard = useCallback(() => {
        depi.saveBlackboard();
    }, []);

    const onClearBlackboard = useCallback(() => {
        depi.clearBlackboard();
    }, []);

    const onRefreshModel = useCallback(() => {
        if (dependencyGraph.resource) {
            depi.requestDependencyGraph(dependencyGraph.resource, branchName);
            return;
        }
        depi.requestDepiModel(branchName);
        depi.requestBlackboard();
    }, [dependencyGraph.resource, branchName]);

    const onSwitchBranch = useCallback((newName, isTag) => {
        console.log('cannot switch branch', newName, isTag);
    }, []);

    const onRemoveEntriesFromBlackboard = useCallback(
        (selectedEntries) => {
            // console.log(JSON.stringify(selectedEntries, null, 2));
            const removedResources = [];
            const removedLinks = [];

            const entries = selectedEntries
                .map(({ isLink, entry }) => {
                    if (isLink) {
                        const link = blackboardModel.links.find((l) => isSameLink(entry, l));
                        removedLinks.push(link);
                        return link;
                    }

                    const resource = blackboardModel.resources.find((r) => isSameResource(entry, r));
                    removedResources.push(resource);
                    return resource;
                })
                .concat(getAdditionalLooseLinks(blackboardModel.links, removedResources, removedLinks));

            depi.removeEntriesFromBlackboard(entries);
        },
        [blackboardModel]
    );

    const onDeleteEntriesFromDepi = useCallback(
        (selectedEntries) => {
            // console.log(JSON.stringify(selectedEntries, null, 2));
            const deletedResources = [];
            const deletedLinks = [];

            const entries = selectedEntries.map(({ isLink, entry }) => {
                if (isLink) {
                    const link = depiModel.links.find((l) => isSameLink(entry, l));
                    const sourceResource = depiModel.resources.find((r) => isSameResource(r, link.source));
                    const targetResource = depiModel.resources.find((r) => isSameResource(r, link.target));
                    const linkRef = {
                        source: getResourceRefFromResource(sourceResource, depiModel.resourceGroups),
                        target: getResourceRefFromResource(targetResource, depiModel.resourceGroups),
                    };

                    deletedLinks.push(linkRef);
                    return linkRef;
                }

                const resourceRef = getResourceRefFromResource(
                    depiModel.resources.find((r) => isSameResource(entry, r)),
                    depiModel.resourceGroups
                );

                deletedResources.push(resourceRef);
                return resourceRef;
            });

            getAdditionalLooseLinks(depiModel.links, deletedResources, deletedLinks).forEach((link) => {
                const sourceResource = depiModel.resources.find((r) => isSameResource(r, link.source));
                const targetResource = depiModel.resources.find((r) => isSameResource(r, link.target));
                entries.push({
                    source: getResourceRefFromResource(sourceResource, depiModel.resourceGroups),
                    target: getResourceRefFromResource(targetResource, depiModel.resourceGroups),
                });
            });

            depi.deleteEntriesFromDepi(entries);
        },
        [depiModel]
    );

    const onRevealInEditor = useCallback((resource) => {
        depi.revealInEditor(resource);
    }, []);

    const onViewResourceDiff = useCallback((resource, lastCleanVersion) => {
        depi.viewResourceDiff(resource, lastCleanVersion);
    }, []);

    const onMarkLinksClean = useCallback((links, propagate) => {
        depi.markLinksClean(links, propagate);
    }, []);

    const onMarkInferredDirtinessClean = useCallback((link, dirtinessSource, propagate) => {
        depi.markInferredDirtinessClean(link, dirtinessSource, propagate);
    }, []);

    const onMarkAllClean = useCallback((links) => {
        depi.markAllClean(links);
    }, []);

    const onEditResourceGroup = useCallback((resourceGroupRef, updateDesc, remove) => {
        depi.editResourceGroup(resourceGroupRef, updateDesc, remove);
    }, []);

    // Graphical and navigation callbacks.
    const onShowBlackboard = useCallback(() => {
        setDependencyGraph({ resource: null, links: [], dependants: false });
        depi.requestDepiModel(branchName);
        depi.requestBlackboard();
    }, [branchName]);

    const onShowDependencyGraph = useCallback(
        (resource, dependants) => {
            depi.requestDependencyGraph(resource, branchName, dependants);
        },
        [branchName]
    );

    const onWidthChange = useCallback((w) => {
        setMenuItemWidth(w);
    }, []);

    const menuItems = useMemo(() => {
        const menuItems = [];

        menuItems.push({
            icon: <NotesIcon />,
            title: 'View/edit fields',
            content: (
                <EditorForm
                    isReadOnly={isReadOnly}
                    isBlackboardEmpty={blackboardModel.resources.length + blackboardModel.links.length === 0}
                    selection={selection}
                    onRevealInEditor={onRevealInEditor}
                    onViewResourceDiff={onViewResourceDiff}
                    onRemoveEntriesFromBlackboard={onRemoveEntriesFromBlackboard}
                    onDeleteEntriesFromDepi={onDeleteEntriesFromDepi}
                    setSelection={setSelection}
                    onMarkLinksClean={onMarkLinksClean}
                    onMarkInferredDirtinessClean={onMarkInferredDirtinessClean}
                    onMarkAllClean={onMarkAllClean}
                    onShowDependencyGraph={onShowDependencyGraph}
                    onEditResourceGroup={onEditResourceGroup}
                />
            ),
        });

        if (!dependencyGraph.resource) {
            menuItems.push({
                icon: <SearchIcon />,
                title: 'Search tree',
                content: <TreeBrowser width={menuItemWidth} depiModel={depiModel} setSelection={setSelection} />,
            });
        }

        return menuItems;
    }, [
        isReadOnly,
        menuItemWidth,
        blackboardModel,
        depiModel,
        selection,
        dependencyGraph,
        onRevealInEditor,
        onViewResourceDiff,
        onRemoveEntriesFromBlackboard,
        onDeleteEntriesFromDepi,
        setSelection,
        onMarkLinksClean,
        onMarkInferredDirtinessClean,
        onMarkAllClean,
        onShowDependencyGraph,
        onEditResourceGroup,
    ]);

    if (errorMessage) {
        return (
            <div
                id="graph-container"
                style={{
                    height: '100vh',
                    width: '100vw',
                    backgroundColor: darkMode ? '#121212' : '#fff',
                    padding: '16px',
                }}
            >
                {errorMessage}
            </div>
        );
    }

    // console.log('selection', JSON.stringify(selection, null, 2));

    return (
        <div
            id="graph-container"
            style={{ height: '100vh', width: '100vw', backgroundColor: darkMode ? '#121212' : '#fff' }}
        >
            <AppBarHeader
                isReadOnly={isReadOnly}
                layoutOpts={layoutOpts}
                branchName={branchName}
                branchesAndTags={branchesAndTags}
                resource={dependencyGraph.resource}
                dependants={dependencyGraph.dependants}
                depiModel={depiModel}
                blackboardModel={blackboardModel}
                showDirtyness={showDirtyness}
                setShowDirtyness={setShowDirtyness}
                onSaveBlackboard={onSaveBlackboard}
                onClearBlackboard={onClearBlackboard}
                onRefreshModel={onRefreshModel}
                onShowBlackboard={onShowBlackboard}
                onShowDependencyGraph={onShowDependencyGraph}
                onSwitchBranch={onSwitchBranch}
            />
            {dependencyGraph.resource ? (
                <DependencyGraph
                    isReadOnly={isReadOnly}
                    width={centerPanelWidth}
                    height={size.height - layoutOpts.headerHeight}
                    showDirtyness={showDirtyness}
                    resource={dependencyGraph.resource}
                    links={dependencyGraph.links}
                    dependants={dependencyGraph.dependants}
                    selection={selection}
                    setSelection={setSelection}
                />
            ) : (
                <BlackboardGraph
                    isReadOnly={isReadOnly}
                    toolsConfig={toolsConfig}
                    width={centerPanelWidth}
                    height={size.height - layoutOpts.headerHeight}
                    depiModel={depiModel}
                    onExpandResourceGroups={onExpandResourceGroups}
                    onCollapseResourceGroups={onCollapseResourceGroups}
                    showDirtyness={showDirtyness}
                    blackboardModel={blackboardModel}
                    onLinkResources={onLinkResources}
                    selection={selection}
                    setSelection={setSelection}
                />
            )}

            <SideMenu
                layoutOpts={layoutOpts}
                menuItems={menuItems}
                bottomActionEls={[]}
                left={0}
                totalWidth={size.width}
                sideMenuIndex={sideMenuIndex}
                onWidthChange={onWidthChange}
                setSideMenuIndex={setSideMenuIndex}
            />
        </div>
    );
}
