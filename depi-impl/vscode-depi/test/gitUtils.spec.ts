import { parseResourceGroupUrl } from '../src/gitUtils';

describe('gitUtils', () => {
    describe('parseResourceGroupUrl', () => {
        it('should parse standard gitlab ssh url', () => {
            const url = 'git@git.isis.vanderbilt.edu:aa-caid/depi-impl.git';
            const { host, owner, name, hostName, hostPrefix, isSsh } = parseResourceGroupUrl(url);
            expect(isSsh).toBe(true);
            expect(host).toBe('git@git.isis.vanderbilt.edu');
            expect(hostName).toBe('git.isis.vanderbilt.edu');
            expect(hostPrefix).toBe('git@');
            expect(owner).toBe('aa-caid');
            expect(name).toBe('depi-impl');
        });

        it('should parse standard github ssh url', () => {
            const url = 'git@github.com:webgme/webgme.git';
            const { host, owner, name, hostName, hostPrefix, isSsh } = parseResourceGroupUrl(url);
            expect(isSsh).toBe(true);
            expect(host).toBe('git@github.com');
            expect(hostName).toBe('github.com');
            expect(hostPrefix).toBe('git@');
            expect(owner).toBe('webgme');
            expect(name).toBe('webgme');
        });

        it('should parse aliased ssh url', () => {
            const url = 'git-vandy:VUISIS/p-state-visualizer.git';
            const { host, owner, name, hostName, hostPrefix, isSsh } = parseResourceGroupUrl(url);
            expect(isSsh).toBe(true);
            expect(host).toBe('git-vandy');
            expect(hostName).toBe('git-vandy');
            expect(hostPrefix).toBe('');
            expect(owner).toBe('VUISIS');
            expect(name).toBe('p-state-visualizer');
        });

        it('should parse gitlab https url', () => {
            const url = 'https://git.isis.vanderbilt.edu/aa-caid/depi-impl.git';
            const { host, owner, name, hostName, hostPrefix, isSsh } = parseResourceGroupUrl(url);
            expect(isSsh).toBe(false);
            expect(host).toBe('https://git.isis.vanderbilt.edu');
            expect(hostName).toBe('git.isis.vanderbilt.edu');
            expect(hostPrefix).toBe('https://');
            expect(owner).toBe('aa-caid');
            expect(name).toBe('depi-impl');
        });

        it('should parse local http url', () => {
            const url = 'http://localhost:3001/patrik/c-sources.git';
            const { host, owner, name, hostName, hostPrefix, isSsh } = parseResourceGroupUrl(url);
            expect(isSsh).toBe(false);
            expect(host).toBe('http://localhost:3001');
            expect(hostName).toBe('localhost:3001');
            expect(hostPrefix).toBe('http://');
            expect(owner).toBe('patrik');
            expect(name).toBe('c-sources');
        });
    });
});
