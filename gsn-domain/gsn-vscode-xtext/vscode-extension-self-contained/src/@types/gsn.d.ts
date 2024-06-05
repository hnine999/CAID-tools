import { Uri } from 'vscode';
import { UndoRedoEntry } from '../undoRedo';
import GsnDepi from '../GsnDepi';
import GsnReview from '../GsnReview';

export interface ModelContext {
    modelHash: string,
    dirUri: Uri,
    gsnDepi: GsnDepi,
    gsnReview: GsnReview,
    undoStack: UndoRedoEntry[],
    redoStack: UndoRedoEntry[],
}

export interface Label {
    name: string,
    description: string,
    isGroup: boolean,
    parent?: string|null,
    members?: string[],
}

export interface View {
    id: string,
    timestamp: number,
    expression: string,
    includeSubtrees: boolean,
    includeParents: boolean,
    expandAll: boolean,
    highlightMatches: boolean

}

export interface Comment {
    comment: string,
    timestamp: number,
    user: {
        name: string,
        email: string,
    }
}

export interface CommentUpdate {
    uuid: string,
    isNew: boolean,
    comment?: string,
    timestamp?: number,
}