#!/usr/bin/env python3
"""Process the complete recording, retaining every usable disconnected component.

Runtime paths and logs are private. summary.json is a path-free public report.
Training produces provisional candidates; visual review is required to publish.
No scene alignment, interpolation of missing geometry, or automatic publication.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time

from repair_scene import model_names, save


def windows(frames, duration, width=30, stride=20):
    if not frames or not 0 < stride <= width or duration <= frames[-1]['timestamp']:
        raise ValueError('Invalid complete-recording window inventory')
    rows = []
    start = 0
    while start < duration:
        end = min(start + width, duration)
        names = [f['name'] for f in frames if start <= f['timestamp'] < end]
        rows.append({'id': f'window-{start:06.1f}', 'start': start, 'end': end,
                     'names': names})
        if end == duration:
            break
        start += stride
    if set().union(*(set(w['names']) for w in rows)) != {f['name'] for f in frames}:
        raise ValueError('Window plan omits source frames')
    return rows


class Campaign:
    def __init__(self, args):
        self.a = args
        self.root = args.work.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = (self.root / '.lock').open('a')
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.scripts = Path(__file__).resolve().parent
        self.frames = json.loads((args.source_run / 'frames.json').read_text())
        self.times = {f['name']: f['timestamp'] for f in self.frames}
        if len(self.times) != len(self.frames):
            raise ValueError('Duplicate source frames')
        self.plan = windows(self.frames, args.duration)
        config = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
        config['script_hashes'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in self.scripts.glob('*.py')}
        config['frames_sha256'] = hashlib.sha256((args.source_run/'frames.json').read_bytes()).hexdigest()
        self.path = self.root/'state.json'
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {
            'config': config, 'started': time.time(), 'stages': {}, 'components': [], 'windows': []}
        if self.state['config'] != config:
            raise ValueError('Configuration changed; use a fresh campaign directory')
        self.checkpoint()

    def checkpoint(self):
        self.state['updated'] = time.time()
        save(self.path, self.state)
        components = [{k: v for k, v in c.items() if k not in ('path', 'names')}
                      for c in self.state['components']]
        covered = set().union(*(set(c['names']) for c in self.state['components']
                               if c['status'] in ('published-existing', 'trained-awaiting-review')))
        bins = []
        for start in range(0, int(self.a.duration)+1, 10):
            fs = [f for f in self.frames if start <= f['timestamp'] < start+10]
            bins.append({'start': start, 'end': min(start+10, self.a.duration),
                         'source_frames': len(fs), 'frames_in_trained_models': sum(f['name'] in covered for f in fs)})
        save(self.root/'summary.json', {'duration_seconds': self.a.duration,
            'source_frames': len(self.frames), 'started': self.state['started'], 'updated': self.state['updated'],
            'finished': self.state.get('finished'), 'status': self.state.get('status', 'running'),
            'window_count': len(self.plan), 'windows': self.state['windows'],
            'components': components, 'frames_in_trained_models': len(covered),
            'coverage_bins': bins,
            'warning': 'Registered frames and temporal spans do not prove complete surfaces. New candidates require visual review; scenes are not joined.'})

    def headroom(self):
        if shutil.disk_usage(self.root).free < 20 * 1024**3:
            raise RuntimeError('Disk below 20 GiB: campaign paused, retained results unchanged')
        available = int(next(l.split()[1] for l in Path('/proc/meminfo').read_text().splitlines()
                             if l.startswith('MemAvailable:')))
        if available < 8*1024**2:
            raise RuntimeError('Memory below 8 GiB: campaign paused')

    def run(self, key, command, outputs):
        previous = self.state['stages'].get(key)
        if previous:
            if previous['status'] == 'passed' and all(p.exists() for p in outputs):
                return True
            if previous['status'] != 'failed':
                raise RuntimeError(f'{key}: interrupted stage or missing accepted output; '
                                   'inspect retained log and recover in a fresh campaign')
            # Observed failures remain recorded, without automatic retries.
            return False
        self.headroom()
        logs = self.root/'logs'; logs.mkdir(exist_ok=True)
        row = {'status': 'running', 'started': time.time()}
        self.state['stages'][key] = row
        self.checkpoint()
        print(key, 'started', flush=True)
        with (logs/(key+'.log')).open('w') as log:
            result = subprocess.run(list(map(str, command)), stdout=log, stderr=subprocess.STDOUT,
                env=dict(os.environ, OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='2'))
        ok = result.returncode == 0 and all(p.exists() for p in outputs)
        row.update(status='passed' if ok else 'failed', finished=time.time(), exit_code=result.returncode)
        self.checkpoint()
        print(key, row['status'], flush=True)
        return ok

    def python(self, script, *args):
        return [sys.executable, self.scripts/script, *args]

    def component(self, model, origin, published=False):
        names = model_names(model/'images.bin')
        if not names or not set(names) <= self.times.keys():
            raise ValueError('Component references unknown source frames')
        identity = hashlib.sha256((model/'images.bin').read_bytes()).hexdigest()[:16]
        existing = next((c for c in self.state['components'] if c['id'] == identity), None)
        if existing and existing['status'] != 'pending':
            return
        if existing is None:
            ts = sorted(self.times[n] for n in names)
            existing = {'id': identity, 'origin': origin, 'path': str(model), 'names': names,
                'registered_frames': len(names), 'start': ts[0], 'end': ts[-1],
                'status': 'published-existing' if published else 'pending'}
            # Account for every candidate. Only omit training if ALL its views
            # occur in one already trained model, never discard novel frames.
            if not published:
                for c in self.state['components']:
                    if c['status'] in ('published-existing', 'trained-awaiting-review') and set(names) <= set(c['names']):
                        existing.update(status='reused-covered', covered_by=c['id'], novel_frames=0)
                        break
            self.state['components'].append(existing)
            self.checkpoint()
        c = existing
        if published or c['status'] == 'reused-covered':
            return
        work = self.root/'components'/identity
        work.mkdir(parents=True, exist_ok=True)
        prepared = work/'prepared'; dataset = prepared/'dataset'; training = work/'training'
        def stage(label, command, outputs):
            ok = self.run(identity+'-'+label, command, outputs)
            if not ok:
                c.update(status='failed', failed_stage=label)
                self.checkpoint()
            return ok
        if not stage('prepare', self.python('prepare_component.py', '--model', model,
            '--source-run', self.a.source_run, '--work', prepared, '--colmap', self.a.colmap,
            '--start', c['start'], '--end', c['end']+0.000001), [dataset/'sparse/images.bin']):
            if (prepared/'quality.json').exists():
                c['quality'] = {k:v for k,v in json.loads((prepared/'quality.json').read_text()).items()
                                if not k.endswith('_names')}
                self.checkpoint()
            return
        c['quality'] = {k:v for k,v in json.loads((prepared/'quality.json').read_text()).items()
                        if not k.endswith('_names')}
        if not stage('mask', self.python('mask_people.py', dataset), [dataset/'mask-report.json']): return
        if not stage('mask-check', self.python('inspect_masks.py', dataset, work/'mask-review.jpg'), [work/'mask-review.jpg']): return
        c['mask_visual_review'] = 'pending; automated batch training is provisional'
        if not stage('train', self.python('video_to_splat.py', '--stage', 'train', '--dataset', dataset,
            '--output', training, '--brush', self.a.brush, '--steps', 8000,
            '--train-resolution', 1920, '--max-splats', 500000, '--eval-split-every', 10), [training/'splats/scene.ply']): return
        renders = training/'splats/eval_8000'
        if not stage('evaluate', self.python('inspect_brush.py', dataset, renders, training/'inspection',
            '--expected-views', (len(names)+9)//10), [training/'inspection/held-out.json']): return
        text_model = prepared/'dataset-model-text'; text_model.mkdir(exist_ok=True)
        if not stage('camera-export', [self.a.colmap, 'model_converter', '--input_path', dataset/'sparse',
            '--output_path', text_model, '--output_type', 'TXT'], [text_model/'images.txt']): return
        if not stage('references', self.python('prepare_references.py', '--dataset', dataset,
            '--model-text', text_model, '--held-out-renders', renders, '--training-state', training/'state.json',
            '--output', training/'references', '--train-stride', 20), [training/'references/views.json']): return
        metric = json.loads((training/'inspection/held-out.json').read_text())
        ply = training/'splats/scene.ply'
        c.update(status='trained-awaiting-review', static_region_psnr_db=metric['static_region_psnr_db'],
                 held_out_views=metric['held_out_views'], ply_bytes=ply.stat().st_size,
                 ply_sha256=hashlib.sha256(ply.read_bytes()).hexdigest())
        self.checkpoint()

    def execute(self):
        # Published components first, then all retained window models, largest
        # first so smaller overlapping copies do not consume training time.
        for model in self.a.published_model:
            self.component(Path(model), 'previously published', published=True)
        candidates = list(self.a.windows.glob('window-*/refined/images.bin'))
        candidates += list((self.a.source_run/'sparse').glob('*/images.bin'))
        candidates.sort(key=lambda p: len(model_names(p)), reverse=True)
        for p in candidates:
            self.component(p.parent, 'retained camera reconstruction')
        database = self.root/'database.db'
        if not database.exists():
            self.headroom()
            # SQLite backup includes committed WAL content and leaves input read-only.
            with sqlite3.connect(f'file:{self.a.database.resolve()}?mode=ro', uri=True) as src:
                with sqlite3.connect(database.with_suffix('.partial')) as dst:
                    src.backup(dst)
            database.with_suffix('.partial').replace(database)
        with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as db:
            ids = {name: iid for iid, name in db.execute('SELECT image_id,name FROM images')}
        for window in self.plan:
            wid = window['id']
            if any(w['id'] == wid and w['status'] != 'running' for w in self.state['windows']): continue
            row = next((w for w in self.state['windows'] if w['id'] == wid), None)
            if row is None:
                row = {k:v for k,v in window.items() if k != 'names'}
                row.update(status='running', source_frames=len(window['names']))
                self.state['windows'].append(row)
            covered = set().union(*(set(c['names']) for c in self.state['components']
                                   if c['status'] in ('published-existing', 'trained-awaiting-review')))
            missing = set(window['names'])-covered
            if not missing:
                row.update(status='reused', uncovered_frames=0); self.checkpoint(); continue
            folder = self.root/wid; folder.mkdir(exist_ok=True)
            (folder/'images.txt').write_text('\n'.join(window['names'])+'\n')
            pairs = []
            for i, name in enumerate(window['names']):
                for offset in (1, 2, 4, 8, 16, 32):
                    if i+offset < len(window['names']):
                        other = window['names'][i+offset]
                        if name in missing or other in missing:
                            if name not in ids or other not in ids: raise ValueError('Missing database features')
                            pairs.append(name+' '+other)
            (folder/'pairs.txt').write_text('\n'.join(pairs)+'\n')
            row['uncovered_frames_before'] = len(missing)
            if not self.run(wid+'-match', [self.a.colmap, 'matches_importer', '--database_path', database,
                '--match_list_path', folder/'pairs.txt', '--match_type', 'pairs', '--SiftMatching.use_gpu', 1,
                '--SiftMatching.num_threads', 4], [database]):
                row['status'] = 'failed-matching'; self.checkpoint(); continue
            models = folder/'models'; models.mkdir(exist_ok=True)
            if not self.run(wid+'-map', [self.a.colmap, 'mapper', '--database_path', database,
                '--image_path', self.a.source_run/'images', '--image_list_path', folder/'images.txt',
                '--output_path', models, '--Mapper.multiple_models', 1, '--Mapper.max_num_models', 50,
                '--Mapper.min_model_size', 20, '--Mapper.num_threads', 4,
                '--Mapper.init_min_tri_angle', 8, '--Mapper.filter_max_reproj_error', 3,
                '--Mapper.ba_global_frames_ratio', 1.5, '--Mapper.ba_global_points_ratio', 1.5], [models]):
                row['status'] = 'failed-mapping'; self.checkpoint(); continue
            found = sorted(models.glob('*/images.bin'), key=lambda p: len(model_names(p)), reverse=True)
            row['models_found'] = len(found)
            for model in found:
                self.component(model.parent, wid)
            row['status'] = 'processed' if found else 'no-camera-model'
            self.checkpoint()
        self.state.update(finished=time.time(), status='processing-finished-review-required')
        self.checkpoint()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source-run', 'windows', 'database', 'work'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--colmap', required=True)
    p.add_argument('--brush', required=True)
    p.add_argument('--published-model', action='append', default=[])
    p.add_argument('--duration', type=float, default=737.301333)
    a = p.parse_args()
    campaign = Campaign(a)
    try:
        campaign.execute()
    except BaseException:
        campaign.state['status'] = 'interrupted-see-private-log'
        campaign.checkpoint()
        raise


if __name__ == '__main__':
    main()
