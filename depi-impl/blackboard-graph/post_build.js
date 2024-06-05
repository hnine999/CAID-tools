/* eslint-disable no-restricted-syntax */
const fs = require('fs-extra');
const path = require('path');

const BUILD_DIR = './build';
const OUT_DIR = path.join('../vscode-depi', 'out');

const staticDirSrc = path.join(BUILD_DIR, 'static');
const assetManifestSrc = path.join(BUILD_DIR, 'asset-manifest.json');

const staticDirDst = path.join(OUT_DIR, 'static');
const assetManifestDst = path.join(OUT_DIR, 'asset-manifest.json');

fs.removeSync(staticDirDst);
fs.removeSync(assetManifestDst);

fs.copySync(staticDirSrc, staticDirDst);
fs.copySync(assetManifestSrc, assetManifestDst);

// This is somewhat temporary -> need the style for the diff view
const DIFF_2_HTML_CSS = 'diff2html.min.css';
fs.copySync(path.join('./src/style', DIFF_2_HTML_CSS), path.join(OUT_DIR, DIFF_2_HTML_CSS));
