"""Generate short PCM WAV effects locally, using only the standard library."""
import json
import math
from pathlib import Path
import struct
import wave
import shutil
import subprocess
import tempfile


def main():
    root = Path(__file__).parent
    settings = json.loads((root / 'data/game.json').read_text())['sound']
    output = root / 'sounds'
    output.mkdir(exist_ok=True)
    rate = settings['sample_rate']
    for name, notes in settings['notes'].items():
        samples = bytearray()
        for frequency, duration in notes:
            count = round(rate * duration)
            for i in range(count):
                t = i / rate
                envelope = min(1, t / 0.005) * (1 - i / count) ** 2
                value = math.sin(math.tau * frequency * t)
                samples.extend(struct.pack('<h', round(32767 * settings['amplitude'] * envelope * value)))
        with wave.open(str(output / f'{name}.wav'), 'wb') as sound:
            sound.setnchannels(1)
            sound.setsampwidth(2)
            sound.setframerate(rate)
            sound.writeframes(samples)
    print(f"Created {len(settings['notes'])} short WAV effects in sounds/.")
    # macOS provides speech generation; the game only needs the finished WAVs.
    if shutil.which('say') and shutil.which('afconvert'):
        with tempfile.TemporaryDirectory() as temporary:
            for name, sentence in settings['speech'].items():
                source = str(Path(temporary) / f'{name}.aiff')
                subprocess.run(['say', '-r', str(settings['speech_rate']), '-o', source, sentence], check=True)
                subprocess.run(['afconvert', '-f', 'WAVE', '-d', 'LEI16', source,
                                str(output / f'{name}.wav')], check=True)
        print(f"Created {len(settings['speech'])} spoken sentences in sounds/.")
    else:
        print('Speech generation needs macOS say and afconvert; existing voice files are kept.')


if __name__ == '__main__':
    main()
