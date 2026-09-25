// Used only by render_evaluation.mjs; settings match the pinned viewer engine.
import * as pc from 'playcanvas';
const canvas = document.getElementById('canvas');
window.renderEvaluation = async (view) => {
    const device = await pc.createGraphicsDevice(canvas, {
        deviceTypes: ['webgl2'], antialias: false, preserveDrawingBuffer: true
    });
    const app = new pc.Application(canvas, {graphicsDevice: device});
    app.setCanvasResolution(pc.RESOLUTION_FIXED, view.width, view.height);
    app.scene.gsplat.radialSorting = true;
    app.scene.gsplat.antiAlias = true;
    app.scene.gsplat.minContribution = 1;
    app.scene.gsplat.alphaClip = 1 / 255;
    app.scene.gsplat.renderer = pc.GSPLAT_RENDERER_RASTER_CPU_SORT;
    const camera = new pc.Entity('camera');
    camera.addComponent('camera', {clearColor: new pc.Color(0, 0, 0), nearClip: .01,
        farClip: 1000, fov: view.fov, gammaCorrection: pc.GAMMA_SRGB,
        toneMapping: pc.TONEMAP_NONE});
    app.root.addChild(camera);
    camera.setPosition(...view.position);
    camera.lookAt(new pc.Vec3(...view.target), new pc.Vec3(...view.up));
    const asset = await new Promise((resolve, reject) => app.assets.loadFromUrl(
        '/scene.ply', 'gsplat', (error, value) => error ? reject(error) : resolve(value)));
    const splat = new pc.Entity('splat');
    splat.setEulerAngles(0, 0, 180);
    splat.addComponent('gsplat', {asset});
    app.root.addChild(splat);
    const frames = new Promise(resolve => {
        let count = 0;
        app.on('postrender', () => { if (++count === 12) resolve(); });
    });
    app.start();
    await frames;
    return {position: camera.getPosition().toArray(), fov: camera.camera.fov};
};
