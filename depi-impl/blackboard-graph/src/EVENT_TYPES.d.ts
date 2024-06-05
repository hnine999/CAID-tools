export declare const EVENT_TYPES: {
    // Events from graph to vscode
    // -- Request state
    REQUEST_TOOLS_CONFIG: string;
    REQUEST_DEPI_MODEL: string;
    REQUEST_BLACKBOARD_MODEL: string;
    REQUEST_DEPENDENCY_GRAPH: string;
    REQUEST_BRANCHES_AND_TAGS: string;
    EXPAND_RESOURCE_GROUPS: string;
    COLLAPSE_RESOURCE_GROUPS: string;
    // -- Depi actions
    LINK_RESOURCES: string;
    SAVE_BLACKBOARD: string;
    CLEAR_BLACKBOARD: string;
    REMOVE_ENTRIES_FROM_BLACKBOARD: string,
    DELETE_ENTRIES_FROM_DEPI: string,
    MARK_LINKS_CLEAN: string,
    MARK_INFERRED_DIRTINESS_CLEAN: string,
    MARK_ALL_CLEAN: string,
    EDIT_RESOURCE_GROUP: string,
    // -- UI events
    REVEAL_IN_EDITOR: string;
    VIEW_RESOURCE_DIFF: string;

    // Events from vscode
    TOOLS_CONFIG: string;
    DEPI_MODEL: string;
    BLACKBOARD_MODEL: string;
    DEPENDENCY_GRAPH: string;
    ERROR_MESSAGE: string;
    BRANCHES_AND_TAGS: string;
};