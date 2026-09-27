import { build } from 'esbuild';
import { mkdir, copyFile } from 'node:fs/promises';
await mkdir('dist/stitch-editor', {recursive:true});
await build({entryPoints:['src/stitch-editor.js'], bundle:true, minify:true, format:'esm', target:'es2022', outfile:'dist/stitch-editor/editor.js', legalComments:'eof', external:['node:worker_threads']});
await copyFile('public/stitch-editor/index.html','dist/stitch-editor/index.html');
