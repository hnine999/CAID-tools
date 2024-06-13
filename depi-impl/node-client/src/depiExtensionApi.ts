import * as vscode from 'vscode';
import { Resource } from './@types/depi';
import { DepiSession, logInDepiClientWithToken, logOut } from './depiUtils';

const DEPI_EXTENSION_ID = 'vu-isis.depi';

export interface TokenLoginData {
    userName: string;
    token: string;
    url: string;
    certificate: string;
    options: any;
}

export default class DepiExtensionApi {
    depiExtensionActivated: boolean = false;
    depiExtensionUnavailable: boolean = false;
    log: Function;
    session: DepiSession | null = null;

    constructor(log: Function) {
        this.log = log;
    }

    private tryActivateDepiExtension = async () => {
        try {
            let depiExtension = vscode.extensions.getExtension(DEPI_EXTENSION_ID);
            if (!depiExtension) {
                throw new Error(`Could not find "${DEPI_EXTENSION_ID}" extension`);
            }

            if (depiExtension.isActive) {
                return true;
            }

            await depiExtension.activate();
            return true;
        } catch (err) {
            console.error(err);
            this.log('tryActivateDepiExtension', err);
            this.depiExtensionUnavailable = true;
            return false;
        }
    }

    private async ensureDepiExtensionAvailable() {
        if (this.depiExtensionUnavailable || (!this.depiExtensionActivated && !await this.tryActivateDepiExtension())) {
            throw new Error('Depi extension not reachable!');
        }
    }

    /**
     * Get the login data for the current user.
     * @returns 
     */
    async getDepiToken(): Promise<TokenLoginData> {
        await this.ensureDepiExtensionAvailable();
        return await vscode.commands.executeCommand('depi.getDepiToken');
    }

    /**
     * Get the current depi-session or login and create a new one if none available.
     * @param forceNew - destory current session and create a new one.
     * @returns 
     */
    async getDepiSession(forceNew: boolean = false): Promise<DepiSession> {
        if (this.session && !forceNew) {
            return this.session;
        }

        if (forceNew) {
            await this.destroy();
        }

        const tokenLogin = await this.getDepiToken();

        this.session = await logInDepiClientWithToken(
            tokenLogin.url,
            tokenLogin.token,
            tokenLogin.certificate,
            tokenLogin.options
        );
        return this.session;
    }

    /**
     * Logout and destroy session.
     */
    async destroy() {
        if (this.session) {
            await logOut(this.session);
            this.session = null;
        }
    }

    /**
     * Brings up the blackboard view.
     * @param branchName - optionally pass if you don't want to use the branch in the depi-session.
     */
    async showBlackboard(branchName?: string) {
        await this.ensureDepiExtensionAvailable();
        let branch = branchName;
        if (!branch) {
            const session = await this.getDepiSession();
            branch = session.branchName;
        }

        await vscode.commands.executeCommand('depi.showBlackboard', branch);
    }

    /**
     * Bring ups the dependency graph for the given resource.
     * @param resource 
     * @param branchName 
     */
    async showDependencyGraph(resource: Resource, branchName?: string) {
        await this.ensureDepiExtensionAvailable();
        let branch = branchName;
        if (!branch) {
            const session = await this.getDepiSession();
            branch = session.branchName;
        }

        await vscode.commands.executeCommand('depi.showDependencyGraph', resource, branch);
    }

    /**
     * Bring ups the dependants graph (reverse dependency graph) for the given resource.
     * @param resource 
     * @param branchName 
     */
    async showDependantsGraph(resource: Resource, branchName?: string) {
        await this.ensureDepiExtensionAvailable();
        let branch = branchName;
        if (!branch) {
            const session = await this.getDepiSession();
            branch = session.branchName;
        }

        await vscode.commands.executeCommand('depi.showDependantsGraph', resource, branch);
    }

    /**
     * Lets the user select a resource from a list by first selecting resource group and then resource.
     * @returns A resource if one was selected, otherwise null.
     */
    async selectDepiResource(): Promise<Resource | null> {
        await this.ensureDepiExtensionAvailable();
        return await vscode.commands.executeCommand('depi.selectDepiResource');
    }

    /**
     * Calls out to reveal a resource and the depi-extension delegates this to any installed extension that matches the
     * resource tool of the resource. (If the tool is git, the depi-extension will handle it directly.)
     * @param resource 
     */
    async revealDepiResource(resource: Resource) {
        await this.ensureDepiExtensionAvailable();
        await vscode.commands.executeCommand('depi.revealDepiResource', resource);
    }
}