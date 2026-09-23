"""Bundle an already verified application release for one-time root approval."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def build(platform, release, output):
    if output.exists():
        raise ValueError('Output must be new')
    output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix='aoc-maintenance-build-') as temporary:
        stage = Path(temporary)
        if any(path.is_symlink() or not (path.is_file() or path.is_dir())
               for path in (release, *release.rglob('*'))):
            raise ValueError('Release links and special files are forbidden')
        shutil.copytree(release, stage / 'release')
        if any(path.is_symlink() for path in stage.rglob('*')):
            raise ValueError('Release symlinks are forbidden')
        shutil.copyfile(Path(__file__).with_name('aoc-maintain.py'), stage / 'aoc-maintain.py')
        if platform == 'spark':
            (stage / 'open5gs/compose').mkdir(parents=True)
            for name in ('runtime.py', 'upgrade_connectivity.py'):
                shutil.copyfile(ROOT / 'stacks/open5gs/compose' / name, stage / 'open5gs/compose' / name)
            shutil.copyfile(ROOT / 'stacks/open5gs/artifacts.lock.json', stage / 'open5gs/artifacts.lock.json')
        files = {str(path.relative_to(stage)): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in sorted(stage.rglob('*')) if path.is_file()}
        (stage / 'manifest.json').write_text(json.dumps({'schema_version': 1, 'platform': platform,
                                                        'files': files}, sort_keys=True, indent=2) + '\n')
        archive = output / 'approved.tar.gz'
        with tarfile.open(archive, 'x:gz') as target:
            for path in sorted(stage.rglob('*')):
                if path.is_file():
                    target.add(path, arcname=str(path.relative_to(stage)), recursive=False)
        shutil.copyfile(Path(__file__).with_name('bootstrap.py'), output / 'bootstrap.py')
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        (output / 'approved.sha256').write_text(digest + '  approved.tar.gz\n')
        print(json.dumps({'platform': platform, 'archive': str(archive), 'sha256': digest}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('platform', choices=('jetson', 'spark'))
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.platform, args.release, args.output)
