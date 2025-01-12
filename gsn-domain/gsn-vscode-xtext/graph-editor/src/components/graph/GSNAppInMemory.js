import PropTypes from 'prop-types';
import { useState, useCallback, useEffect, useMemo } from 'react';
import { produceWithPatches, enablePatches } from 'immer';

// components
import GSNEditor from './GSNEditor';

// utils
import GSN_CONSTANTS from './GSN_CONSTANTS';
import modelUtils from './modelUtils';
import ConfirmChangeDialog from './ChangeConfirmation/ConfirmChangeDialog';
import getDeleteImplications, { CMDS, getParentId } from './ChangeConfirmation/getDeleteImplications';
import {
    getNewLabelsAfterDeletion,
    getNewLabelsAfterRenaming,
    getDeleteLabelImplications,
    getRenameLabelImplications,
} from './TopMenu/labelUtils';
import { StartStopReviewButton, UndoRedoButtons } from './SideMenuButtons';

// --------------------------------------------------------------------------------

const { SOLVED_BY, IN_CONTEXT_OF } = GSN_CONSTANTS.RELATION_TYPES;

enablePatches();

const USER_PREFERENCES = {
    enforceUniqueNames: true,
};

GSNAppInMemory.propTypes = {
    model: PropTypes.array.isRequired,
    views: PropTypes.array,
    labels: PropTypes.array,
    width: PropTypes.number,
    height: PropTypes.number,
    isReadOnly: PropTypes.bool,
    updateGlobalState: PropTypes.func,
};

function mockEvidenceInfo() {
    const val = Math.random();
    if (val < 0.25) {
        return {
            status: GSN_CONSTANTS.NODE_DEPI_STATES.NO_DEPI_RESOURCE,
            evidence: [],
        };
    }
    if (val < 0.5) {
        return {
            status: GSN_CONSTANTS.NODE_DEPI_STATES.NO_LINKED_EVIDENCE,
            evidence: [],
        };
    }
    if (val <= 0.75) {
        return {
            status: GSN_CONSTANTS.NODE_DEPI_STATES.RESOURCE_DIRTY,
            evidence: [
                {
                    name: 'artifact.zip',
                    toolId: 'git',
                    url: '/folder/subfolder/subsubfolder/artifact.zip',
                    resourceGroupUrl: 'http://github.com/demo/test-results.git',
                    resourceGroupVersion: '18a611815e3c6a5b14c29662d6d3e002268a0e88',
                },
            ],
        };
    }
    return {
        status: GSN_CONSTANTS.NODE_DEPI_STATES.RESOURCE_UP_TO_DATE,
        evidence: [
            {
                name: 'artifact.zip',
                toolId: 'git',
                url: '/folder/subfolder/subsubfolder/artifact.zip',
                resourceGroupUrl: 'http://github.com/demo/test-results.git',
                resourceGroupVersion: '18a611815e3c6a5b14c29662d6d3e002268a0e88',
            },
            {
                name: 'artifact2.zip',
                toolId: 'git',
                url: '/folder/artifact2.zip',
                resourceGroupUrl: 'http://github.com/demo/test-results.git',
                resourceGroupVersion: '18a611815e3c6a5b14c29662d6d3e002268a0e88',
            },
        ],
    };
}

const depiMethods = {
    addAsResource: ({ nodeId, uuid }) => {
        console.log('addAsResource', uuid, '@', nodeId);
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve();
            });
        });
    },
    removeAsResource: ({ nodeId, uuid }) => {
        console.log('removeAsResource', uuid, '@', nodeId);
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve();
            });
        });
    },
    linkEvidence: ({ nodeId, uuid }) => {
        console.log('linkEvidence', uuid, '@', nodeId);
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve();
            });
        });
    },
    unlinkEvidence: ({ nodeId, uuid }, evidence) => {
        console.log('unlinkEvidence', uuid, '@', nodeId, 'evidence', evidence);
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve();
            });
        });
    },
    showDependencyGraph: ({ nodeId, uuid }) => {
        console.log('showDependencyGraph', uuid, '@', nodeId);
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve();
            });
        });
    },
    revealEvidence: (resource) => {
        console.log('revealEvidence', resource);
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve();
            });
        });
    },
    getEvidenceInfo: ({ nodeId, uuid }) =>
        new Promise((resolve) => {
            console.log('getEvidenceInfo', uuid, '@', nodeId);
            setTimeout(() => {
                resolve(mockEvidenceInfo());
            }, 50);
        }),
    getAllResources: () => {
        const res = {};
        modelMock
            .filter((n) => n.type === GSN_CONSTANTS.TYPES.SOLUTION)
            .forEach(({ uuid }) => {
                res[uuid] = mockEvidenceInfo();
            });

        return new Promise((resolve) => {
            setTimeout(() => {
                resolve(res);
            });
        });
    },
};

let modelMock = null;

export default function GSNAppInMemory({ isReadOnly, model, views, labels, width, height, updateGlobalState }) {
    const [selectedNode, setSelectedNode] = useState({ nodeId: null, treeId: null });
    const [pendingChanges, setPendingChanges] = useState([]);
    const [comments, setComments] = useState({});
    const [depiResources, setDepiResources] = useState(null);
    const [reviewTag, setReviewTag] = useState('');

    useEffect(() => {
        depiMethods
            .getAllResources()
            .then((res) => {
                setDepiResources(res);
            })
            .catch(console.error);
    }, [model]);

    modelMock = model;
    // Event handlers from editing model
    const onAttributeChange = useCallback(
        (nodeId, attr, newValue, additionalNodeIds = []) => {
            let msg = null;

            const [newModel, , invPatches] = produceWithPatches(model, (draftModel) => {
                const idToNode = modelUtils.getIdToNodeMap(draftModel);
                const nodeData = idToNode[nodeId];

                // Hack to make sure all nodes have a uuid.
                draftModel.forEach((node) => {
                    if (!node.uuid) {
                        node.uuid = crypto.randomUUID();
                    }

                    delete node.namespace;
                });

                if (attr === 'name') {
                    const newId = modelUtils.getNewIdAtNameChange(nodeId, newValue);
                    const oldIdsToNew = modelUtils.getNewIdsForNodeAndChildren(draftModel, nodeId, newId);
                    nodeData.name = newValue;

                    draftModel.forEach((node) => {
                        if (oldIdsToNew.has(node.id)) {
                            node.id = oldIdsToNew.get(node.id);
                        }

                        // Update any relations to pointing to the old ids.
                        oldIdsToNew.forEach((newId, oldId) => {
                            let idx = (node[IN_CONTEXT_OF] || []).indexOf(oldId);
                            if (idx !== -1) {
                                node[IN_CONTEXT_OF][idx] = newId;
                                node[IN_CONTEXT_OF].sort();
                            }

                            idx = (node[SOLVED_BY] || []).indexOf(oldId);
                            if (idx !== -1) {
                                node[SOLVED_BY][idx] = newId;
                                node[SOLVED_BY].sort();
                            }
                        });
                    });

                    msg = `Changed id of ${nodeId} to ${newId}.`;
                } else {
                    msg = `Updated ${attr} of ${nodeId} to "`;
                    if (typeof newValue === 'string' && newValue.length > 15) {
                        msg += `${newValue.substring(0, 15)}...".`;
                    } else {
                        msg += `${newValue}".`;
                    }

                    nodeData[attr] = newValue;
                    additionalNodeIds.forEach((id) => {
                        idToNode[id][attr] = newValue;
                    });
                }
            });

            updateGlobalState('model', newModel, getCommitObj(invPatches, msg, 'update'));
        },
        [model, updateGlobalState]
    );

    const onNewChildNode = useCallback(
        (nodeId, relationType, childType, childId = null) => {
            let msg;
            let type = 'creation';
            const [newModel, , invPatches] = produceWithPatches(model, (draftModel) => {
                const parentNode = draftModel.find((n) => n.id === nodeId);

                if (!childId) {
                    const newName = modelUtils.generateUniqueChildName(
                        modelUtils.getShortTypeName(childType),
                        draftModel.map((n) => n.name)
                    );
                    childId = `${parentNode.id}/${newName}`;
                    const newChild = {
                        id: childId,
                        uuid: crypto.randomUUID(),
                        type: childType,
                        name: newName,
                    };

                    newChild.summary = '';

                    draftModel.push(newChild);
                    msg = `Created and added `;
                } else {
                    type = 'update';
                    msg = 'Added ';
                }

                msg += `${childId} as a ${relationType} to ${nodeId}.`;

                parentNode[relationType] = parentNode[relationType] || [];
                parentNode[relationType] = parentNode[relationType].filter((id) => id !== childId);
                parentNode[relationType].push(childId);
                parentNode[relationType].sort();
            });

            updateGlobalState('model', newModel, getCommitObj(invPatches, msg, type));
        },
        [model, updateGlobalState]
    );

    const onDeleteConnection = useCallback(
        (srcId, relationType, dstId) => {
            if (getParentId(dstId) === srcId) {
                setPendingChanges(getDeleteImplications(dstId, model));
                return;
            }

            const [newModel, , invPatches] = produceWithPatches(model, (draftModel) => {
                const parentNode = draftModel.find((n) => n.id === srcId);
                const index = parentNode[relationType].findIndex((id) => id === dstId);
                if (index !== -1) {
                    parentNode[relationType].splice(index, 1);
                }
            });

            updateGlobalState(
                'model',
                newModel,
                getCommitObj(invPatches, `Removed ${dstId} as a ${relationType} from ${srcId}.`, 'update')
            );
        },
        [model, updateGlobalState]
    );

    const onDeleteNode = useCallback(
        (nodeId /* nodeType */) => {
            const changes = getDeleteImplications(nodeId, model);

            if (changes) {
                setPendingChanges(changes);
            }
        },
        [model]
    );

    const onAddNewView = useCallback(
        (newView) => {
            const newViews = [newView, ...views];
            updateGlobalState('views', newViews);
        },
        [views, updateGlobalState]
    );

    const onDeleteView = useCallback(
        (viewId) => {
            const newViews = views.filter((view) => view.id !== viewId);
            updateGlobalState('views', newViews);
        },
        [views, updateGlobalState]
    );

    const onRenameView = useCallback(
        (viewId, name) => {
            const newViews = views.map((view) => {
                if (view.id !== viewId) {
                    return view;
                }

                const updatedView = { ...view };
                updatedView.name = name;

                return updatedView;
            });

            updateGlobalState('views', newViews);
        },
        [views, updateGlobalState]
    );

    const onAddNewLabel = useCallback(
        (newLabel) => {
            const newLabels = [newLabel, ...labels];
            updateGlobalState('labels', newLabels);
        },
        [labels, updateGlobalState]
    );

    const onDeleteLabel = useCallback(
        (name) => {
            const deletedLabel = labels.find((l) => l.name === name);
            if (!deletedLabel.isGroup) {
                getDeleteLabelImplications(model, name).forEach((change) => {
                    onAttributeChange(change.nodeId, 'labels', change.newValue);
                });
            }

            const newLabels = getNewLabelsAfterDeletion(labels, name);
            console.log('old', labels);
            console.log('new', newLabels);
            updateGlobalState('labels', newLabels);
        },
        [labels, model, onAttributeChange, updateGlobalState]
    );

    const onUpdateLabel = useCallback(
        (oldName, newLabel) => {
            let newLabels;

            if (newLabel.name !== oldName) {
                if (!newLabel.isGroup) {
                    getRenameLabelImplications(model, newLabel.name, oldName).forEach((change) => {
                        onAttributeChange(change.nodeId, 'labels', change.newValue);
                    });
                }

                newLabels = getNewLabelsAfterRenaming(labels, newLabel, oldName);
            } else {
                newLabels = labels.map((label) => {
                    if (label.name !== oldName) {
                        return label;
                    }

                    return newLabel;
                });
            }

            updateGlobalState('labels', newLabels);
        },
        [labels, model, onAttributeChange, updateGlobalState]
    );

    const onAddNewComment = useCallback((uuid, comment) => {
        setComments((prevComments) => {
            const newComments = { ...prevComments };
            if (!newComments[uuid]) {
                newComments[uuid] = [];
            }

            newComments[uuid].unshift({
                comment,
                timestamp: Date.now(),
                user: {
                    name: 'nebuchadnezzar',
                    email: 'em@il.com',
                },
            });

            return newComments;
        });
    }, []);

    const onDeleteComment = useCallback((uuid, timestamp) => {
        setComments((prevComments) => {
            const newComments = { ...prevComments };
            newComments[uuid] = (prevComments[uuid] || []).filter((comment) => comment.timestamp !== timestamp);

            if (newComments[uuid].length === 0) {
                delete newComments[uuid];
            }

            return newComments;
        });
    }, []);

    const onOk = () => {
        const [newModel, , invPatches] = produceWithPatches(model, (draftModel) => {
            const idToNode = modelUtils.getIdToNodeMap(draftModel);

            pendingChanges.forEach(({ cmd, nodeId, ...rest }) => {
                if (cmd === CMDS.ON_REMOVE_CHILD_REF) {
                    const { childId, relationType } = rest;
                    const node = idToNode[nodeId];
                    const idx = node[relationType].findIndex((id) => id === childId);
                    node[relationType].splice(idx, 1);
                } else if (cmd === CMDS.ON_DELETE_NODE) {
                    const idx = draftModel.findIndex((node) => node.id === nodeId);
                    draftModel.splice(idx, 1);
                    // In the gsn-files the parent will be cleaned out by the removal of the child
                    // however on the json array we need to clear that relation explicitly.
                    const { nodeType } = rest;
                    const parentId = nodeId.split('/').slice(0, -1).join('/');
                    const parentNode = idToNode[parentId];
                    if (parentNode) {
                        const relationType = GSN_CONSTANTS.CONTEXT_NODES.includes(nodeType) ? IN_CONTEXT_OF : SOLVED_BY;
                        const idx = parentNode[relationType].findIndex((id) => id === nodeId);
                        parentNode[relationType].splice(idx, 1);
                    }
                }
            });
        });

        updateGlobalState('model', newModel, getCommitObj(invPatches, `Deleted nodes from model.`, 'removal'));
        setSelectedNode({ nodeId: null, treeId: null });
        setPendingChanges([]);
    };

    const sideMenuActionBtns = useMemo(
        () => [
            ...UndoRedoButtons({ undoRedo: { undo: 2, redo: 1 }, onUndo: () => {}, onRedo: () => {} }),
            StartStopReviewButton({
                onStartReview: () => {
                    setReviewTag('v1.0.0');
                },
                onStopReview: () => {
                    setReviewTag(null);
                },
                reviewTag,
            }),
        ],
        [reviewTag]
    );

    const onCancel = () => {
        setPendingChanges([]);
    };

    return (
        <>
            {pendingChanges.length > 0 ? (
                <ConfirmChangeDialog model={model} changes={pendingChanges} onOk={onOk} onCancel={onCancel} />
            ) : null}
            <GSNEditor
                userPreferences={USER_PREFERENCES}
                reviewTag={reviewTag}
                model={model}
                views={views}
                labels={labels}
                comments={comments}
                depiResources={depiResources}
                width={width}
                height={height}
                isReadOnly={isReadOnly}
                extraSideMenuBottomActionEls={sideMenuActionBtns}
                selectedNode={selectedNode}
                setSelectedNode={setSelectedNode}
                onAttributeChange={onAttributeChange}
                onNewChildNode={onNewChildNode}
                onDeleteConnection={onDeleteConnection}
                onDeleteNode={onDeleteNode}
                onAddNewView={onAddNewView}
                onDeleteView={onDeleteView}
                onRenameView={onRenameView}
                onAddNewLabel={onAddNewLabel}
                onDeleteLabel={onDeleteLabel}
                onUpdateLabel={onUpdateLabel}
                onAddNewComment={onAddNewComment}
                onDeleteComment={onDeleteComment}
                depiMethods={depiMethods}
            />
        </>
    );
}

const getCommitObj = (invPatches, title, type) => ({
    id: `#${Math.round(Math.random() * 10000000)}`,
    title,
    type,
    time: Date.now(),
    invPatches,
});
