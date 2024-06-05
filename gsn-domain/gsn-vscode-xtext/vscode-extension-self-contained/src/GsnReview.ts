import * as vscode from 'vscode';
import { API as GitAPI } from './@types/git';
import GsnDepi from './GsnDepi';
import { tryFindGitRepoForUri, gitCommit, gitStageAll, gitPushWithTags, gitPush } from './gitUtils';
import { readInReviewInfo, writeOutReviewInfo } from './util';

/**
 * Methods used during review process.
 * One instance is created and kept alive as long as the panel is.
 * During model-context switch - the dirUri needs to be updated.
 */
export default class GsnReview {
    localGit = false;
    log: Function;
    git: GitAPI;
    dirUri: vscode.Uri;
    gsnDepi?: GsnDepi;

    constructor(git: GitAPI, dirUri: vscode.Uri, log: Function, gsnDepi?: GsnDepi) {
        this.git = git;
        this.dirUri = dirUri;
        this.log = log;
        this.gsnDepi = gsnDepi;
    }

    updateModelDir = (dirUri: vscode.Uri) => {
        this.log('Updating dirUri for GsnReview');
        this.dirUri = dirUri;
    }

    getReviewInfo = async () => {
        const info = await readInReviewInfo(this.dirUri);
        if (info.tag) {
            this.log(`Found review tag ${info.tag}!`);
            this.gsnDepi && await this.gsnDepi.switchToBranch(info.tag);
        } else {
            this.log('No review tag - continue in normal mode.');
        }

        return info;
    }

    startReview = async ({ tag }: { tag: string }) => {
        await writeOutReviewInfo(this.dirUri, { tag });
        this.gsnDepi && await this.gsnDepi.switchToBranch(tag);
    }

    stopReview = async ({ tag, submit }: { tag: string, submit: boolean }) => {
        if (submit) {
            const repo  = await tryFindGitRepoForUri(this.git, this.dirUri);
            if (!repo) {
                vscode.window.showErrorMessage('The opened gsn model is not in a git repo - cannot submit review.');
                return;
            }

            const logRepoState = (msg: string) => {
                this.log(msg, 'working-tree:', repo.state.workingTreeChanges.length, 'index:',
                    repo.state.indexChanges.length);
            }

            await repo.status();

            logRepoState('Starting submission.');

            if (repo.state.workingTreeChanges.length > 0 || repo.state.indexChanges.length > 0) {
                // TODO: How to check remote state (more than with just depi).
                vscode.window.showErrorMessage('Cannot submit review! Local changes need to be commited and pushed.');
                return;
            }

            const commitVersion = repo.state.HEAD?.commit;
            let depiReport = false;
            if (this.gsnDepi) {
                const rgGroup = await this.gsnDepi.getResourceGroup();
                if (rgGroup) {
                    if (commitVersion !== rgGroup.version) {
                        this.log('Local commit-version does not match depi resource-group',
                            commitVersion, '!=', rgGroup.version);
                        vscode.window.showErrorMessage('Cannot submit review! Local version does not match version of resource-group in depi.');
                        return;
                    }

                    depiReport = true;
                }
            }


            const { tag } = await readInReviewInfo(this.dirUri);

            if (!tag) {
                vscode.window.showErrorMessage('The opened gsn model is not in a review - nothing to submit.');
                return;
            }

            // await gitStageAll(repo);
            // let commitVersion = repo.state.HEAD?.commit;
            // if (repo.state.indexChanges.length === 0) {
            //     this.log('No need to commit');
            // } else {
            //     await gitCommit(repo);
            //     commitVersion = repo.state.HEAD?.commit;
            //     logRepoState('Commited uncommited changes.');
            //     vscode.window.showInformationMessage(`Commited staged state to local git repo.`);
            // }

            // if (repo.state.indexChanges.length > 0) {
            //     vscode.window.showInformationMessage('Submission aborted - local changes needs to be committed.');
            //     return;
            // }

            try {
                await repo.tag(tag, 'Review submitted from GSN Assurance editor');
                this.log('Created tag', tag);
                vscode.window.showInformationMessage(`Created tag ${tag} at #${commitVersion.substring(0, 8)} - pushing..`);
            } catch (err) {
                this.log(err.message);
                vscode.window.showErrorMessage('Failed to create tag - submission aborted!');
                return;
            }

            try {
                await gitPushWithTags(repo);
            } catch (err) {
                this.log(err.message);
                vscode.window.showErrorMessage('Failed to push tag - aborting.');
                return;
            }

            if (depiReport) {
                // // Ping depi to ensure new version has been registered.
                // let remoteVersion = 'N/A';
                // let tryCnt = 0;
                // const MAX_TRIES = 30;
                // const SLEEP_SECONDS = 2;

                // function sleep() {
                //     return new Promise(resolve => setTimeout(resolve, SLEEP_SECONDS * 1000));
                // }

                // while (remoteVersion !== commitVersion) {
                //     tryCnt += 1;
                //     await sleep();
                //     if (tryCnt > MAX_TRIES) {
                //         vscode.window.showErrorMessage('Failed to find new version in depi.');
                //         return;
                //     }

                //     vscode.window.showInformationMessage(`Waiting for depi `);
                // }
                await this.gsnDepi.convertBranchToTag(tag);
            }

            await writeOutReviewInfo(this.dirUri, { tag: null });
            await repo.status();
            logRepoState('Removed tag from review info.');
            await gitStageAll(repo);
            await gitCommit(repo);
            logRepoState('Committed removed tag.');

            while (repo.state.indexChanges.length > 0) {
                vscode.window.showErrorMessage('The updated review info needs to be committed.');
                await gitCommit(repo);
                logRepoState('Committed inside commit loop!');
            }

            await gitPush(repo);
        } else {
            await writeOutReviewInfo(this.dirUri, { tag: null });
            this.gsnDepi && await this.gsnDepi.deleteBranch(tag);
        }
    }
}