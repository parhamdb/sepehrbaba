#!/usr/bin/env python3
"""Migrate receipts only across the known loop frame-count serialization fix.

Requires an idle run. Verifies every saved prediction, preserves original
metadata, and changes only adapter identity; missing loop receipts stay missing.
The resumed runner still validates all actual inputs and model/config hashes.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import time
from run_da3_full import digest, save

PREVIOUS_SHA256 = 'b53c4e000c44fa9e14f694b1ad4c518cad90f1f8691fe3e41e25ea0c22cd5e03'
OLD = 'count=range_1[1]-range_1[0]+(range_2[1]-range_2[0] if range_2 else 0)'
NEW = 'count=int(range_1[1]-range_1[0]+(range_2[1]-range_2[0] if range_2 else 0))'


def migrate(output, previous_adapter, adapter, expected_chunks=799):
    if digest(previous_adapter) != PREVIOUS_SHA256:
        raise ValueError('Not the known previous adapter')
    old_source = previous_adapter.read_bytes()
    if old_source.count(OLD.encode()) != 1 or adapter.read_bytes() != old_source.replace(OLD.encode(), NEW.encode()):
        raise ValueError('Adapter changes exceed the serialization-only fix')
    with (output / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        original = json.loads((output / 'inputs.json').read_text())
        if original['adapter_sha256'] != PREVIOUS_SHA256:
            raise ValueError('Run does not use the known previous adapter')
        updated = dict(original, adapter_sha256=digest(adapter))
        identity = lambda data: hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        old_identity, new_identity = identity(original), identity(updated)
        sequential = output / '_tmp_results_unaligned'
        if {p.name for p in sequential.glob('chunk_*.receipt.json')} != {f'chunk_{i}.receipt.json' for i in range(expected_chunks)}:
            raise ValueError('Incomplete sequential checkpoint inventory')
        records = {}
        paths = sorted(sequential.glob('*.receipt.json')) + sorted((output / '_tmp_results_loop').glob('*.receipt.json'))
        for path in paths:
            data = json.loads(path.read_text())
            prediction = path.with_name(path.name.replace('.receipt.json', '.npy'))
            if data['identity'] != old_identity or data['sha256'] != digest(prediction):
                raise ValueError(f'Invalid prediction receipt: {path.name}')
            records[str(path.relative_to(output))] = data
        backup = output / 'loop-int64-migration-backup.json'
        if backup.exists():
            raise FileExistsError('Migration backup already exists; inspect before retrying')
        save(backup, dict(inputs=original, receipts=records))
        try:
            for name, data in records.items():
                save(output / name, dict(data, identity=new_identity))
            save(output / 'inputs.json', updated)
            report = dict(status='migrated', timestamp=time.time(), previous_adapter_sha256=PREVIOUS_SHA256,
                          adapter_sha256=updated['adapter_sha256'], old_identity=old_identity, new_identity=new_identity,
                          sequential_receipts=expected_chunks, loop_receipts=len(paths)-expected_chunks,
                          predictions_hash_verified=len(paths), inference_settings_changed=False)
            save(output / 'loop-int64-migration.json', report)
        except Exception:
            for name, data in records.items():
                save(output / name, data)
            save(output / 'inputs.json', original)
            raise
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('output', 'previous-adapter', 'adapter'):
        parser.add_argument('--' + key, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(migrate(args.output, args.previous_adapter, args.adapter), indent=2))
