"""Rebuild GitHub Pages output. Requires pygbag and FFmpeg on the build machine."""
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).parent.resolve()
for source in (root / 'sounds').glob('*.wav'):
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(source),
                    '-ac', '2', '-c:a', 'vorbis', '-strict', 'experimental', '-q:a', '4', str(source.with_suffix('.ogg'))], check=True)
subprocess.run([sys.executable, '-m', 'pygbag', '--build', '.'], cwd=root, check=True)
shutil.copytree(root / 'build/web', root / 'docs', dirs_exist_ok=True)
(root / 'docs/.nojekyll').touch()
print('GitHub Pages files ready in docs/.')
