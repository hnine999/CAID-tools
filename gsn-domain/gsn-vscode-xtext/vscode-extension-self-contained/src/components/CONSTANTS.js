export default {
    EVENTS: {
        TYPES: {
            STATE_UPDATE: 'STATE_UPDATE',
            DEPI_CMD: 'DEPI_CMD',
            REVIEW_CMD: 'REVIEW_CMD',
            REVEAL_ORIGIN: 'REVEAL_ORIGIN',
            REQUEST_MODEL: 'REQUEST_MODEL',
            REQUEST_VIEWS: 'REQUEST_VIEWS',
            REQUEST_LABELS: 'REQUEST_LABELS',
            REQUEST_COMMENTS: 'REQUEST_COMMENTS',
            REQUEST_DEPI_RESOURCES: 'REQUEST_DEPI_RESOURCES',
            ERROR_MESSAGE: 'ERROR_MESSAGE',
            UNDO: 'UNDO',
            REDO: 'REDO',
            UNDO_REDO_AVAILABLE: 'UNDO_REDO_AVAILABLE',
        },
        STATE_TYPES: {
            LABELS: 'labels',
            VIEWS: 'views',
            MODEL: 'model',
            COMMENTS: 'comments',
            DEPI_RESOURCES: 'depiResources',
        },
        DEPI_CMD_TYPES: {
            GET_EVIDENCE_INFO: 'getEvidenceInfo',
            ADD_AS_RESOURCE: 'addAsResource',
            REMOVE_AS_RESOURCE: 'removeAsResouce',
            UNLINK_EVIDENCE: 'unlinkEvidence',
            LINK_EVIDENCE: 'linkEvidence',
            SHOW_DEPENDENCY_GRAPH: 'showDependencyGraph',
            REVEAL_EVIDENCE: 'revealEvidence',
            GET_ALL_RESOURCES: 'getAllResources',
        }, 
        REVIEW_CMD_TYPES: {
            GET_REVIEW_INFO: 'getReviewInfo',
            START_REVIEW: 'startReview',
            STOP_REVIEW: 'stopReview',
        }
    }
};
