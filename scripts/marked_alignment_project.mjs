#!/usr/bin/env node
// Convert a raw-PLY similarity into a reversible editor project placement.
import { readFile, writeFile } from 'node:fs/promises';
import { Mat4, Quat, Vec3 } from 'playcanvas';

const [projectPath, fitsPath, outputPath] = process.argv.slice(2);
if (!projectPath || !fitsPath || !outputPath) {
  throw new Error('Usage: node scripts/marked_alignment_project.mjs PROJECT.json FITS.json OUTPUT.json');
}
const input = JSON.parse(await readFile(projectPath, 'utf8'));
const project = structuredClone(input.project ?? input);
const fit = JSON.parse(await readFile(fitsPath, 'utf8'))['floor-direction'];
const earlier = project.scenes.find(s => s.id === 'earlier-tracked');
const later = project.scenes.find(s => s.id === 'later-tracked');
if (!earlier || !later || project.scenes.length !== 2) throw new Error('Expected the tracked section pair');
if (!(fit?.scale > 0)) throw new Error('Missing floor-direction similarity');

function matrix(t) {
  return new Mat4().setTRS(new Vec3(...t.position), new Quat().setFromEulerAngles(...t.rotation),
    new Vec3(t.scale, t.scale, t.scale));
}
const similarity = new Mat4();
for (let col = 0; col < 3; col++) {
  for (let row = 0; row < 3; row++) similarity.data[col * 4 + row] = fit.scale * fit.rotation[row][col];
  similarity.data[12 + col] = fit.translation[col];
}
// The editor's child rotates each PLY 180 degrees about Z.
const flip = new Mat4().setScale(-1, -1, 1);
const expected = matrix(earlier.transform).mul(flip).mul(similarity).mul(flip);
const scale = expected.getScale();
const rotationMatrix = expected.clone();
for (let col = 0; col < 3; col++) {
  for (let row = 0; row < 3; row++) rotationMatrix.data[col * 4 + row] /= scale.x;
}
const rotation = new Quat().setFromMat4(rotationMatrix).getEulerAngles();
const position = expected.getTranslation();
later.transform = {
  position: [position.x, position.y, position.z],
  rotation: [rotation.x, rotation.y, rotation.z],
  scale: scale.x,
};
const reconstructed = matrix(later.transform);
const error = Math.max(...expected.data.map((v, i) => Math.abs(v - reconstructed.data[i])));
if (!Number.isFinite(error) || error > 1e-5) throw new Error(`Transform round-trip failed: ${error}`);
await writeFile(outputPath, JSON.stringify(project, null, 2) + '\n', { flag: 'wx' });
console.log(JSON.stringify({ variant: 'floor-direction', provisional: true, matrixMaxError: error, transform: later.transform }));
