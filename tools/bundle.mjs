// Bundles the ES modules into one self-contained HTML file (dist/claude-skirt.html): double-click to play offline.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
const order = ['math', 'skirt-profile', 'rig', 'geo', 'anim', 'brain', 'audio', 'render', 'dances.data', 'main'];
const ns = (m) => '__' + m.replace(/[^a-z]/gi, '_');
let js = '';
for (const m of order) {
  let src = readFileSync(`src/${m}.js`, 'utf8');
  const names = [];
  src = src.replace(/^import\s*\{([^}]*)\}\s*from\s*'\.\/([\w.-]+)\.js';?$/gm, (_, list, dep) => `const {${list}} = ${ns(dep)};`);
  src = src.replace(/^export (const|let|function|class) (\w+)/gm, (_, kw, name) => { names.push(name); return `${kw} ${name}`; });
  js += `const ${ns(m)} = (() => {\n${src}\nreturn { ${names.join(', ')} };\n})();\n`;
}
const html = readFileSync('app.html', 'utf8').replace('<script type="module" src="src/main.js"></script>', () => `<script type="module">\n${js}</script>`);
mkdirSync('dist', { recursive: true });
writeFileSync('dist/claude-skirt.html', `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n${html.replace('<div id="app">', '</head>\n<body>\n<div id="app">')}\n</body>\n</html>\n`);
const head = '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n<meta property="og:image" content="https://mywestlord.github.io/claude-skirt/assets/banner.png">\n<meta name="twitter:card" content="summary_large_image">\n<meta property="og:title" content="Claude Skirt">\n<meta property="og:description" content="A bee-bot ballerina in a fake Blender viewport. Order a dance; a fruit-fly brain model steers her spins.">\n';
const page = readFileSync('app.html', 'utf8').replace('<div id="app">', '</head>\n<body>\n<div id="app">');
writeFileSync('index.html', head + page + '\n</body>\n</html>\n');
console.log('index.html written');
console.log('dist/claude-skirt.html', (js.length / 1024).toFixed(0), 'KB of JS');
