import { depiUtils, DepiSession, Resource, ResourceGroupRef } from 'depi-node-client';

interface Watcher {
    branchName: string;
    watcherId: string;
}

const MODEL_TYPES = {
    // eslint-disable-next-line @typescript-eslint/naming-convention
    BLACK_BOARD: 'BLACK_BOARD',
    // eslint-disable-next-line @typescript-eslint/naming-convention
    DEPENDENCY_GRAPH: 'DEPENDENCY_GRAPH',
};

export default class DepiUiModel {
    depiSession: DepiSession;
    log: Function;

    type?: string;
    blackboardWatcher?: Watcher;
    depiWatcher?: Watcher;
    // Context
    resource?: Resource;
    activeResourceGroups?: ResourceGroupRef[];
    dependants?: boolean;

    constructor(depiSession: DepiSession, log: Function) {
        this.depiSession = depiSession;
        this.log = log;
    }

    setStateToBlackboard = async (
        branchName: string,
        sendBlackboardModel: Function,
        sendDepiModel: Function,
        sendError: Function
    ) => {
        const registerWatchers = async (blackboardOnly?: boolean) => {
            if (!blackboardOnly) {
                this.depiWatcher = {
                    watcherId: await depiUtils.watchDepi(
                        this.depiSession,
                        async (data) => {
                            this.log('depiWatcher::data::', data);
                            await sendDepiModel(this.activeResourceGroups as ResourceGroupRef[]);
                        },
                        async (err) => {
                            this.log('depiWatcher::err::', err);
                            await sendError(err);
                        }
                    ),
                    branchName: this.depiSession.branchName,
                };
            }

            if (branchName === 'main') {
                this.blackboardWatcher = {
                    watcherId: await depiUtils.watchBlackboard(
                        this.depiSession,
                        async (data) => {
                            this.log('blackboardWatcher::data::', data);
                            await sendBlackboardModel();
                        },
                        async (err) => {
                            this.log('blackboardWatcher::err::', err);
                            await sendError(err);
                        }
                    ),
                    branchName,
                };
            }
        };

        delete this.resource;
        delete this.dependants;
        this.activeResourceGroups = [];

        if (this.depiSession.branchName !== branchName) {
            this.log('Branch switch from', this.depiSession.branchName, 'to', branchName);
            const currentBranch = await depiUtils.setBranch(this.depiSession, branchName);
            if (!currentBranch) {
                throw new Error(`Branch did not exist in depi [${branchName}]`);
            }
        }

        if (this.type !== MODEL_TYPES.BLACK_BOARD) {
            this.logState('Switching uiModel from:');

            this.type = MODEL_TYPES.BLACK_BOARD;
            this.depiSession.branchName = branchName;

            await this.clearWatchers();
            await registerWatchers();
            this.logState('New uiModel:');
        } else if (this.depiSession.branchName !== branchName) {
            // Only the main branch has a blackboard.
            if (this.blackboardWatcher) {
                await depiUtils.unwatchBlackboard(this.depiSession, this.blackboardWatcher.watcherId);
                delete this.blackboardWatcher;
            }

            registerWatchers(true);
            this.depiSession.branchName = branchName;
        }
    };

    setStateToDependencyGraph = async (
        resource: Resource,
        branchName: string,
        dependants: boolean,
        sendDependencyGraph: Function,
        sendError: Function
    ) => {
        const registerWatcher = async () => {
            this.depiWatcher = {
                watcherId: await depiUtils.watchDepi(
                    this.depiSession,
                    async (data) => {
                        this.log('depiWatcher::data::', data);
                        await sendDependencyGraph(this.resource, this.dependants);
                    },
                    async (err) => {
                        this.log('depiWatcher::err::', err);
                        await sendError(err);
                    }
                ),
                branchName: this.depiSession.branchName,
            };
        };

        this.resource = resource;
        this.dependants = dependants;
        delete this.activeResourceGroups;

        if (this.depiSession.branchName !== branchName) {
            this.log('Branch switch from', this.depiSession.branchName, 'to', branchName);
            const currentBranch = await depiUtils.setBranch(this.depiSession, branchName);
            if (!currentBranch) {
                throw new Error(`Branch did not exist in depi [${branchName}]`);
            }

            this.depiSession.branchName = branchName;
        }

        if (this.type !== MODEL_TYPES.DEPENDENCY_GRAPH) {
            this.logState('Switching uiModel from:');

            this.type = MODEL_TYPES.DEPENDENCY_GRAPH;

            await this.clearWatchers();
            await registerWatcher();
            this.logState('New uiModel:');
        }
    };

    clearWatchers = async () => {
        if (this.blackboardWatcher) {
            await depiUtils.unwatchBlackboard(this.depiSession, this.blackboardWatcher.watcherId);
            delete this.blackboardWatcher;
        }

        if (this.depiWatcher) {
            await depiUtils.unwatchDepi(this.depiSession, this.depiWatcher.watcherId);
            delete this.depiWatcher;
        }
    };

    dispose = async () => {
        await this.clearWatchers();
        this.log('uiModel disposed');
    };

    logState = (preMessage: string) => {
        this.log(
            preMessage,
            this.type || 'None',
            'with context: ',
            JSON.stringify({
                resource: this.resource,
                activeResourceGroups: this.activeResourceGroups,
                dependants: this.dependants,
            })
        );
    };
}
