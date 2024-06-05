import * as vscode from 'vscode';
import { depiUtils, Resource, DepiSession } from 'depi-node-client';

interface TokenLoginData {
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
            let depiExtension = vscode.extensions.getExtension('vanderbilt.depi');
            if (!depiExtension) {
                throw new Error('Could not find "vanderbilt.depi" extension');
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

    async getDepiToken() : Promise<TokenLoginData> {
        await this.ensureDepiExtensionAvailable();
        return await vscode.commands.executeCommand('depi.getDepiToken');
    }

    async getDepiSession(forceNew: boolean = false): Promise<DepiSession> {
        if (this.session && !forceNew) {
            return this.session;
        }

        if (forceNew) {
            await depiUtils.logOut(this.session as DepiSession);
            this.session = null;
        }

        const tokenLogin = await this.getDepiToken();

        this.session = await depiUtils.logInDepiClientWithToken(
            tokenLogin.url,
            tokenLogin.token,
            tokenLogin.certificate,
            tokenLogin.options
        );
        return this.session;
    }

    async destroy() {
        if (this.session) {
            await depiUtils.logOut(this.session);
            this.session = null;
        }
    }

    /**
     * 
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

    async showDependencyGraph (resource: Resource, branchName?: string) {
        await this.ensureDepiExtensionAvailable();
        let branch = branchName;
        if (!branch) {
            const session = await this.getDepiSession();
            branch = session.branchName;
        }

        await vscode.commands.executeCommand('depi.showDependencyGraph', resource, branch);
    }

    async showDependantsGraph(resource: Resource, branchName?: string) {
        await this.ensureDepiExtensionAvailable();
        let branch = branchName;
        if (!branch) {
            const session = await this.getDepiSession();
            branch = session.branchName;
        }

        await vscode.commands.executeCommand('depi.showDependantsGraph', resource, branch);
    }

    async selectDepiResource(): Promise<Resource | null> {
        await this.ensureDepiExtensionAvailable();
        return await vscode.commands.executeCommand('depi.selectDepiResource');
    }

    async revealDepiResource(resource: Resource) {
        await this.ensureDepiExtensionAvailable();
        await vscode.commands.executeCommand('depi.revealDepiResource', resource);
    }
}