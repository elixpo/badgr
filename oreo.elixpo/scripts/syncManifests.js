const fs = require('fs');
const path = require('path');

const ROOT_DIR = path.join(__dirname, '..', '..');
const APPS_DIR = path.join(ROOT_DIR, 'apps');
const MARKET_DIR = path.join(ROOT_DIR, 'apps_market');
const OUT_FILE = path.join(__dirname, '..', 'src', 'data', 'manifests.json');

const manifests = {};

function scanDir(dir) {
    if (!fs.existsSync(dir)) return;
    const items = fs.readdirSync(dir);
    for (const item of items) {
        const itemPath = path.join(dir, item);
        if (fs.statSync(itemPath).isDirectory()) {
            const manifestPath = path.join(itemPath, 'manifest.json');
            if (fs.existsSync(manifestPath)) {
                try {
                    const content = fs.readFileSync(manifestPath, 'utf-8');
                    const data = JSON.parse(content);
                    manifests[item] = data;
                } catch (e) {
                    console.error(`Error parsing ${manifestPath}: ${e.message}`);
                }
            }
        }
    }
}

scanDir(APPS_DIR);
scanDir(MARKET_DIR);

fs.writeFileSync(OUT_FILE, JSON.stringify(manifests, null, 2));
console.log(`Synced ${Object.keys(manifests).length} manifests to ${OUT_FILE}`);
