#!/usr/bin/env python3
"""Freeze COLMAP diagnostics, then render source/overlay/local-path review video.

No pose interpolation, global alignment, camera refinement or reconstruction.
Render requires Pillow, NumPy, OpenCV, PyAV and ffmpeg/ffprobe; no GPU required.
"""
import argparse
from collections import Counter
from fractions import Fraction
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def rotation(q):
    q = np.asarray(q, dtype=float)
    if not np.isfinite(q).all() or abs(np.linalg.norm(q)-1) > .001:
        raise ValueError('Invalid COLMAP quaternion')
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def project(xyz, R, t, camera):
    xyz = np.asarray(xyz, float).reshape(-1, 3)
    cam = xyz @ np.asarray(R).reshape(3, 3).T + t
    with np.errstate(divide='ignore', invalid='ignore'):
        xy = cam[:, :2] / cam[:, 2, None]
        p = camera['params']
        if camera['model'] == 'SIMPLE_RADIAL':
            f, cx, cy, k = p
            xy = xy * (1+k*np.sum(xy*xy, axis=1))[:, None]
            uv = xy * f + [cx, cy]
        elif camera['model'] == 'SIMPLE_PINHOLE':
            f, cx, cy = p
            uv = xy * f + [cx, cy]
        elif camera['model'] == 'PINHOLE':
            fx, fy, cx, cy = p
            uv = xy * [fx, fy] + [cx, cy]
        else:
            raise ValueError('Unsupported camera model')
    valid = (cam[:, 2] > 0) & np.isfinite(uv).all(axis=1)
    return uv, valid


def flow_check(previous, current, xy):
    """Independent LK measurement with a forward/backward consistency screen."""
    import cv2
    xy = np.asarray(xy, np.float32).reshape(-1, 1, 2)
    if not len(xy):
        return np.empty((0, 2)), np.empty(0, bool)
    params = dict(winSize=(21, 21), maxLevel=3,
                  criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, .01))
    moved, status, _ = cv2.calcOpticalFlowPyrLK(previous, current, xy, None, **params)
    back, reverse_status, _ = cv2.calcOpticalFlowPyrLK(current, previous, moved, None, **params)
    moved = moved.reshape(-1, 2)
    keep = (status.ravel() == 1) & (reverse_status.ravel() == 1)
    keep &= np.linalg.norm(back.reshape(-1, 2)-xy.reshape(-1, 2), axis=1) <= 1.
    keep &= np.isfinite(moved).all(axis=1)
    keep &= (moved[:, 0] >= 0) & (moved[:, 0] < current.shape[1])
    keep &= (moved[:, 1] >= 0) & (moved[:, 1] < current.shape[0])
    return moved, keep


def read_component(path, names):
    before = {n: digest(path/n) for n in ('cameras.txt', 'images.txt', 'points3D.txt')}
    cameras = {}
    for line in (path/'cameras.txt').read_text().splitlines():
        if line and not line.startswith('#'):
            r = line.split()
            if r[1] not in ('SIMPLE_RADIAL', 'SIMPLE_PINHOLE', 'PINHOLE'):
                raise ValueError(f'Unsupported camera: {r[1]}')
            cameras[int(r[0])] = dict(model=r[1], width=int(r[2]), height=int(r[3]), params=list(map(float, r[4:])))
    points = {}
    with (path/'points3D.txt').open() as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                r = line.split()
                points[int(r[0])] = (list(map(float, r[1:4])), float(r[7]), len(r[8:])//2)
    images = {}
    with (path/'images.txt').open() as f:
        for line in f:
            if not line.strip() or line.startswith('#'):
                continue
            r = line.split()
            obs = np.fromstring(next(f), sep=' ').reshape(-1, 3)
            if r[9] not in names:
                raise ValueError('Model image absent from native frame manifest')
            camera = cameras[int(r[8])]
            R, t = rotation(list(map(float, r[1:5]))), np.array(r[5:8], float)
            candidates = []
            for x, y, pid in obs:
                point = points.get(int(pid))
                if point and point[2] >= 5 and point[1] <= 2.:
                    candidates.append((int(pid), x, y, point))
            # Persistently favor long tracks, with spatial coverage instead of a
            # dense cluster on one object. IDs remain stable within a component.
            candidates.sort(key=lambda row: (-row[3][2], row[3][1], row[0]))
            chosen, cells, ids = [], Counter(), set()
            for pid, x, y, point in candidates:
                cell = (int(x/camera['width']*6), int(y/camera['height']*8))
                if pid in ids or cells[cell] >= 1:
                    continue
                cells[cell] += 1; ids.add(pid)
                chosen.append([pid, *point[0], float(x), float(y)])
                if len(chosen) == 32:
                    break
            images[r[9]] = dict(R=R.round(12).tolist(), t=t.tolist(),
                                 center=(-R.T@t).tolist(), camera=camera, points=chosen)
    if any(digest(path/n) != h for n, h in before.items()):
        raise RuntimeError('Input model changed while taking snapshot')
    return images, before


def snapshot(args):
    frames = json.loads(args.frames.read_text())
    names = {f['name'] for f in frames}
    if len(names) != len(frames) or any(b['timestamp'] <= a['timestamp'] for a, b in zip(frames, frames[1:])):
        raise ValueError('Frame inventory or timestamps invalid')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise FileExistsError(args.output)
    components, selection = {}, {}
    for item in args.model:
        label, path = item.split('=', 1)
        if not label or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in label) or label in components:
            raise ValueError('Model labels must be unique portable identifiers')
        images, hashes = read_component(Path(path), names)
        components[label] = dict(registered_frames=len(images), model_hashes=hashes,
                                 trajectory=[dict(name=name, center=im['center']) for name, im in sorted(images.items())])
        for name, im in images.items():
            old = selection.get(name)
            # Larger local reconstruction first; fixed tie break. This is only
            # an overlay-source selection, never evidence of alignment/quality.
            if old is None or (len(images), label) > (components[old['component']]['registered_frames'], old['component']):
                selection[name] = dict(component=label, **im)
        print(label, len(images), 'registered frames', flush=True)
    output = dict(schema=1, source_sha256=digest(args.video), source_frames=len(frames),
                  frames_sha256=digest(args.frames), selection='largest supplied component per frame; label tie break',
                  components=components, frames=[dict(**f, pose=selection.get(f['name'])) for f in frames])
    output['posed_frames'] = len(selection)
    with gzip.open(args.output, 'wt') as f:
        json.dump(output, f, separators=(',', ':'))
    print(json.dumps({'source_frames': len(frames), 'posed_frames': len(selection), 'components': len(components)}))


def render(args):
    import av
    import cv2
    from PIL import Image, ImageDraw, ImageFont
    cv2.setNumThreads(2)
    with gzip.open(args.data, 'rt') as f:
        data = json.load(f)
    frames = [f for f in data['frames'] if args.start <= f['timestamp'] < args.end]
    if not frames:
        raise ValueError('No frames in interval')
    if digest(args.video) != data['source_sha256']:
        raise ValueError('Source video checksum changed')
    args.output.mkdir(parents=True, exist_ok=False)
    font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    font = ImageFont.truetype(font_path, 18)
    small = ImageFont.truetype(font_path, 14)
    bold = ImageFont.truetype(font_path, 23)
    W, H, top = 432, 768, 72
    width, height = 1152, 864
    cyan, orange, pink = '#2be5ee', '#ffbb55', '#ff4d9b'
    paths = {}
    for label, component in data['components'].items():
        xyz = np.array([v['center'] for v in component['trajectory']])
        # Fixed isometric projection of LOCAL COLMAP coordinates, not a floor map.
        basis = np.array([[.70710678, 0, -.70710678], [.40824829, -.81649658, .40824829]])
        coords = xyz@basis.T
        lo, hi = coords.min(0), coords.max(0)
        scale = 220/max(float(np.max(hi-lo)), 1e-6)
        pixels = (coords-(lo+hi)/2)*scale+[1008, 470]
        paths[label] = (basis, (lo+hi)/2, scale, pixels, {v['name']: i for i, v in enumerate(component['trajectory'])})
    video_path = args.output/'silent.mp4'
    container = av.open(str(video_path), mode='w', options={'movflags': '+faststart'})
    stream = container.add_stream('libx264', rate=30)
    stream.width, stream.height, stream.pix_fmt = width, height, 'yuv420p'
    stream.time_base = stream.codec_context.time_base = Fraction(1, 1000000)
    stream.codec_context.thread_count = 2
    stream.options = {'crf': '20', 'preset': 'veryfast'}
    previous = None
    rows = []
    origin = frames[0]['timestamp']
    samples = set()
    for i, item in enumerate(frames):
        pose = item['pose']; label = pose['component'] if pose else None
        with Image.open(args.images/item['name']) as image:
            if pose and image.size != (pose['camera']['width'], pose['camera']['height']):
                raise ValueError('Raw source dimensions disagree with camera model')
            source_size = image.size
            image = image.convert('RGB').resize((W, H), Image.Resampling.LANCZOS)
        gray = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
        canvas = Image.new('RGB', (width, height), '#101820')
        canvas.paste(image, (0, top)); canvas.paste(image, (W, top))
        draw = ImageDraw.Draw(canvas)
        t = item['timestamp']; timestamp = f'{int(t)//60:02d}:{t%60:06.3f}'
        draw.text((12, 6), f'Camera tracking review | source {timestamp} | {item["name"]}', font=bold, fill='white')
        draw.text((12, 43), 'SOURCE', font=font, fill='white')
        draw.text((W+12, 43), 'LANDMARK PROJECTION / IMAGE FLOW', font=small, fill=cyan)
        draw.text((880, 43), 'DIAGNOSTIC SNAPSHOT', font=small, fill='white')
        row = dict(name=item['name'], timestamp=t, component=label, flow_count=0)
        switched = pose and previous and previous['label'] != label
        if pose:
            draw.text((880, 90), 'RECOVERED LOCAL POSE', font=font, fill=cyan)
            draw.text((880, 122), label, font=small, fill='white')
            points = np.array(pose['points'], float).reshape(-1, 6)
            uv, valid = project(points[:, 1:4], pose['R'], pose['t'], pose['camera'])
            scale_xy = np.array([W/source_size[0], H/source_size[1]])
            visible = valid & (uv[:, 0] >= 0) & (uv[:, 0] < source_size[0]) & (uv[:, 1] >= 0) & (uv[:, 1] < source_size[1])
            for point, pixel in zip(points[visible], uv[visible]*scale_xy):
                x, y = pixel+[W, top]
                draw.ellipse((x-4, y-4, x+4, y+4), outline=cyan, width=2)
                draw.text((x+5, y-8), str(int(point[0])), font=small, fill=cyan)
            fit = np.linalg.norm(uv[valid]-points[valid, 4:6], axis=1)
            row['landmarks'] = int(visible.sum())
            row['fit_median_source_px'] = float(np.median(fit)) if len(fit) else None
            draw.text((880, 168), f'Landmarks: {int(visible.sum())}', font=font, fill='white')
            if len(fit):
                draw.text((880, 198), f'Fit median: {np.median(fit):.2f} px', font=font, fill='white')
            can_flow = previous and previous['label'] == label and t-previous['time'] <= .20
            if can_flow and len(previous['points']):
                old = previous['points']
                moved, good = flow_check(previous['gray'], gray, old[:, 4:6]*scale_xy)
                predicted, front = project(old[:, 1:4], pose['R'], pose['t'], pose['camera'])
                predicted *= scale_xy
                good &= front & (predicted[:, 0] >= 0) & (predicted[:, 0] < W) & (predicted[:, 1] >= 0) & (predicted[:, 1] < H)
                disagreement = np.linalg.norm((moved[good]-predicted[good])/scale_xy, axis=1)
                row['flow_count'] = int(good.sum())
                if len(disagreement):
                    row['flow_median_source_px'] = float(np.median(disagreement))
                    row['flow_p95_source_px'] = float(np.percentile(disagreement, 95))
                    for a, b in zip(predicted[good], moved[good]):
                        a = a+[W, top]; b = b+[W, top]
                        draw.line((tuple(a), tuple(b)), fill=pink, width=2)
                        draw.ellipse((a[0]-3, a[1]-3, a[0]+3, a[1]+3), outline=cyan, width=2)
                        draw.line((b[0]-3, b[1]-3, b[0]+3, b[1]+3), fill=orange, width=2)
                        draw.line((b[0]-3, b[1]+3, b[0]+3, b[1]-3), fill=orange, width=2)
                    draw.text((880, 236), f'Flow checks: {len(disagreement)}', font=font, fill='white')
                    draw.text((880, 266), f'Flow p95: {np.percentile(disagreement,95):.1f} px', font=font, fill=orange)
            if not row['flow_count']:
                draw.text((880, 236), 'Flow check unavailable', font=small, fill=orange)
            basis, mid, path_scale, path_pixels, indices = paths[label]
            if len(path_pixels) > 1:
                draw.line([tuple(p) for p in path_pixels], fill='#465461', width=2)
            current = (np.asarray(pose['center'])@basis.T-mid)*path_scale+[1008, 470]
            direction = np.asarray(pose['R']).T@np.array([0., 0., 1.])
            direction = direction@basis.T
            tip = current + 30*direction/max(np.linalg.norm(direction), 1e-8)
            draw.line((tuple(current), tuple(tip)), fill=orange, width=4)
            draw.ellipse((*tuple(current-5), *tuple(current+5)), fill=cyan)
            draw.text((880, 330), 'LOCAL CAMERA PATH', font=font, fill='white')
            draw.text((880, 580), 'Dot: camera position', font=small, fill=cyan)
            draw.text((880, 603), 'Line: viewing direction', font=small, fill=orange)
            draw.text((880, 633), 'Local units; no global join', font=small, fill='white')
            if switched:
                draw.rectangle((W, top, 2*W, top+30), fill='#783600')
                draw.text((W+10, top+5), 'COMPONENT CHANGE - UNALIGNED', font=small, fill='white')
                row['component_change'] = True
            previous = dict(label=label, time=t, gray=gray, points=points)
        else:
            draw.rectangle((W, top, 2*W, top+45), fill='#783600')
            draw.text((W+12, top+12), 'NO POSE IN THIS SNAPSHOT', font=font, fill='white')
            draw.text((880, 100), 'NO RECOVERED POSE', font=font, fill=orange)
            draw.text((880, 140), 'No camera interpolation', font=small, fill='white')
            draw.text((880, 166), 'No global path inferred', font=small, fill='white')
            previous = dict(label=None, time=t, gray=gray, points=np.empty((0, 6)))
        draw.text((880, 690), 'Cyan: projected 3D point', font=small, fill=cyan)
        draw.text((880, 717), 'Orange: image-flow target', font=small, fill=orange)
        draw.text((880, 744), 'Pink: disagreement', font=small, fill=pink)
        draw.text((880, 787), 'Motion / blur can also', font=small, fill='white')
        draw.text((880, 810), 'cause disagreement.', font=small, fill='white')
        draw.text((12, 843), 'Fitted landmarks are not independent ground truth. Component paths have unrelated scale/orientation.', font=small, fill='#c1ccd6')
        video_frame = av.VideoFrame.from_image(canvas)
        video_frame.pts = round((t-origin)*1000000)
        video_frame.time_base = Fraction(1, 1000000)
        for packet in stream.encode(video_frame):
            container.mux(packet)
        row['output_pts_us'] = video_frame.pts
        rows.append(row)
        # Retain review stills at intervals, segment starts and the trial interval.
        bucket = int(t//30)
        if bucket not in samples or (pose and (switched or 590.5 <= t <= 590.7)):
            samples.add(bucket)
            stills = args.output/'stills'; stills.mkdir(exist_ok=True)
            canvas.save(stills/(Path(item['name']).stem+'.jpg'), quality=90)
        if i % 200 == 0:
            print(f'rendered {i+1}/{len(frames)} source {timestamp}', flush=True)
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    final = args.output/'camera-review.mp4'
    # Preserve the original audio on a full-length review; bounded previews are silent.
    command = ['ffmpeg', '-nostdin', '-v', 'error', '-i', str(video_path)]
    full = len(frames) == len(data['frames'])
    if full:
        command += ['-i', str(args.video), '-map', '0:v:0', '-map', '1:a:0?', '-c', 'copy']
    else:
        command += ['-map', '0:v:0', '-c', 'copy']
    subprocess.run(command+['-movflags', '+faststart', str(final)], check=True)
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_frames', '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', str(final)]))
    actual = [float(r['best_effort_timestamp_time']) for r in probe['frames']]
    expected = [r['timestamp']-origin for r in rows]
    if len(actual) != len(expected) or max(abs(a-b) for a, b in zip(actual, expected)) > .000002:
        raise RuntimeError('Video frame count or timestamp preservation failed')
    with gzip.open(args.output/'frame-diagnostics.json.gz', 'wt') as f:
        json.dump(rows, f, separators=(',', ':'))
    report = dict(source_sha256=data['source_sha256'], snapshot_sha256=digest(args.data),
                  script_sha256=digest(__file__), video_sha256=digest(final),
                  source_interval=[frames[0]['timestamp'], frames[-1]['timestamp']],
                  frames=len(rows), posed_frames=sum(r['component'] is not None for r in rows),
                  frames_with_flow=sum(r['flow_count'] > 0 for r in rows),
                  component_changes=sum(r.get('component_change', False) for r in rows),
                  timestamp_max_error_seconds=max(abs(a-b) for a, b in zip(actual, expected)),
                  dimensions=[width, height], original_audio_copied=full,
                  versions=dict(av=av.__version__, cv2=cv2.__version__, numpy=np.__version__),
                  status='rendered; visual review required; not camera-accuracy certification')
    (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    video_path.unlink()
    print(json.dumps(report, indent=2), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    s = sub.add_parser('snapshot')
    s.add_argument('--frames', type=Path, required=True)
    s.add_argument('--video', type=Path, required=True)
    s.add_argument('--model', action='append', required=True, help='LABEL=/path/to/COLMAP-text-model')
    s.add_argument('--output', type=Path, required=True)
    r = sub.add_parser('render')
    r.add_argument('--data', type=Path, required=True)
    r.add_argument('--images', type=Path, required=True)
    r.add_argument('--video', type=Path, required=True)
    r.add_argument('--output', type=Path, required=True)
    r.add_argument('--start', type=float, default=0)
    r.add_argument('--end', type=float, default=math.inf)
    args = p.parse_args()
    (snapshot if args.command == 'snapshot' else render)(args)


if __name__ == '__main__':
    main()
