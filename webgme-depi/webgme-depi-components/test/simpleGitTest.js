const fs = require('fs');
const path = require('path');
const simpleGit = require('simple-git');

const git = simpleGit();
const gitUrl = 'http://127.0.0.1:3001/patrik/Evidence.git';
const gitCredUrl = 'http://patrik:password@127.0.0.1:3001/patrik/Evidence.git';

function gitUrlToPath(url) {
    return url.replace(/[\\/:]/g, '_');
}

async function cloneAndPull(repoUrl, repoDirPath, versionOrBranch) {
    let newClone = false;
    if (!fs.existsSync(repoDirPath)) {
        await git.clone(repoUrl, repoDirPath);
        newClone = true;
    }

    const repoGit = simpleGit({baseDir: path.join(process.cwd(), repoDirPath)});

    if (newClone) {
        await repoGit.addConfig('user.name', 'webgmePlugin');
        await repoGit.addConfig('user.email', 'webgmePlugin@mail.com');
    }

    await repoGit.fetch();
    await repoGit.checkout(versionOrBranch);

    return repoGit;
}


cloneAndPull(gitCredUrl, gitUrlToPath(gitUrl), 'main')
    .then(async (gitRepo) => {
        const commitHash = await gitRepo.revparse('HEAD');
        console.log(commitHash);
    })
    .catch(console.error)