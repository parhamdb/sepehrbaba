import { build } from 'esbuild';
import { cp, mkdir, copyFile } from 'node:fs/promises';
await mkdir('dist', { recursive: true });
// PlayCanvas workers support Node as well as browsers. In the browser their
// `self` branch is used; the Node fallback must remain external to this bundle.
await build({entryPoints:['src/app.js'],bundle:true,minify:true,format:'esm',target:'es2022',outfile:'dist/app.js',legalComments:'eof',external:['node:worker_threads']});
await copyFile('index.html','dist/index.html');
await cp('public','dist',{recursive:true});
