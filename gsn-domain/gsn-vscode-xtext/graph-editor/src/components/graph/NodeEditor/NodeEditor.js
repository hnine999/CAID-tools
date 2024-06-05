import PropTypes from 'prop-types';
import { useMemo } from 'react';
// @mui
import { Divider } from '@mui/material';
// components
import AttributeForm from './AttributeForm';
import IconHeader from './IconHeader';
import RelationsEditor from './RelationsEditor';
import NoSelectionInfo from './NoSelectionInfo';
import NodeStateInfo from './NodeStateInfo';
import NodeStatusInfo from './NodeStatusInfo';
import CommentsSection from './CommentsSection';
import CopyrightVandy from '../CopyrightVandy';
// utils
import modelUtils from '../modelUtils';
import GSN_CONSTANTS from '../GSN_CONSTANTS';
import { NodeType, LabelType, DepiMethodsType, NodeCommentsType, ResourceStateType } from '../gsnTypes';
import ArtifactsEditor from './ArtifactsEditor';
// -----------------------------------------------------------------------------------------------

NodeEditor.propTypes = {
    model: PropTypes.arrayOf(NodeType).isRequired,
    labels: PropTypes.arrayOf(LabelType).isRequired,
    comments: PropTypes.objectOf(NodeCommentsType).isRequired,
    depiResources: PropTypes.objectOf(ResourceStateType),
    isReadOnly: PropTypes.bool,
    selectedNode: PropTypes.shape({
        nodeId: PropTypes.string,
        treeId: PropTypes.string,
    }),
    reviewTag: PropTypes.string,
    setSelectedNode: PropTypes.func.isRequired,
    setSubtreeRoot: PropTypes.func.isRequired,
    onAttributeChange: PropTypes.func.isRequired,
    onNewChildNode: PropTypes.func.isRequired,
    onDeleteConnection: PropTypes.func.isRequired,
    onDeleteNode: PropTypes.func.isRequired,
    onAddNewComment: PropTypes.func.isRequired,
    onDeleteComment: PropTypes.func.isRequired,
    onRevealOrigin: PropTypes.func,
    setTopMenuIndex: PropTypes.func.isRequired,
    setSideMenuIndex: PropTypes.func.isRequired,
    depiMethods: DepiMethodsType,
};

export default function NodeEditor({
    model,
    labels,
    comments,
    depiResources,
    isReadOnly,
    selectedNode,
    reviewTag,
    setSelectedNode,
    setSubtreeRoot,
    onAttributeChange,
    onNewChildNode,
    onDeleteNode,
    onDeleteConnection,
    onAddNewComment,
    onDeleteComment,
    onRevealOrigin,
    setTopMenuIndex,
    setSideMenuIndex,
    depiMethods,
}) {
    const reviewMode = Boolean(reviewTag);
    const { nodeData, connData } = useMemo(() => {
        let nodeData = null;
        let connData = null;
        const { nodeId } = selectedNode;
        if (nodeId) {
            nodeData = model.find((n) => n.id === nodeId);
            if (!nodeData) {
                connData = modelUtils.tryParseModelIdOfConn(nodeId);
            }
        }

        return { nodeData, connData };
    }, [selectedNode, model]);

    if (nodeData) {
        return (
            <>
                <IconHeader
                    nodeData={nodeData}
                    isReadOnly={isReadOnly || reviewMode}
                    reviewTag={reviewTag}
                    onDeleteNode={onDeleteNode}
                    setSubtreeRoot={setSubtreeRoot}
                    onRevealOrigin={onRevealOrigin}
                />
                <Divider />
                <AttributeForm
                    nodeData={nodeData}
                    labels={labels}
                    isReadOnly={isReadOnly}
                    reviewTag={reviewTag}
                    model={model}
                    onAttributeChange={onAttributeChange}
                    setTopMenuIndex={setTopMenuIndex}
                    setSideMenuIndex={setSideMenuIndex}
                />
                {depiMethods ? null : (
                    <ArtifactsEditor
                        nodeData={nodeData}
                        isReadOnly={isReadOnly || reviewMode}
                        onAttributeChange={onAttributeChange}
                    />
                )}
                {nodeData.type === GSN_CONSTANTS.TYPES.GOAL ? (
                    <NodeStatusInfo
                        model={model}
                        nodeData={nodeData}
                        isReadOnly={isReadOnly}
                        onAttributeChange={onAttributeChange}
                    />
                ) : null}
                {nodeData.type === GSN_CONSTANTS.TYPES.SOLUTION ? (
                    <>
                        <NodeStatusInfo
                            model={model}
                            nodeData={nodeData}
                            isReadOnly={isReadOnly}
                            onAttributeChange={onAttributeChange}
                        />
                        <NodeStateInfo
                            nodeData={nodeData}
                            depiResources={depiResources}
                            isReadOnly={isReadOnly || reviewMode}
                            onAttributeChange={onAttributeChange}
                            depiMethods={depiMethods}
                        />
                    </>
                ) : null}
                <Divider />
                <CommentsSection
                    nodeData={nodeData}
                    isReadOnly={isReadOnly}
                    nodeComments={comments[nodeData.uuid] || []}
                    onAddNewComment={onAddNewComment}
                    onDeleteComment={onDeleteComment}
                />
                <Divider />
                <RelationsEditor
                    nodeId={selectedNode.nodeId}
                    isReadOnly={isReadOnly || reviewMode}
                    model={model}
                    setSelectedNode={setSelectedNode}
                    onNewChildNode={onNewChildNode}
                    onDeleteConnection={onDeleteConnection}
                />
                <CopyrightVandy />
            </>
        );
    }

    if (connData) {
        return (
            <>
                <IconHeader nodeData={connData} isReadOnly={isReadOnly} onDeleteConnection={onDeleteConnection} />
                <Divider />
                <CopyrightVandy />
            </>
        );
    }

    // This should not happen - but let's leave it for now instead of crashing.
    return <NoSelectionInfo reviewTag={reviewTag} model={model} />;
}
