"""Build crisp 3x pictures. Run locally with Python and Pillow."""
import json
from pathlib import Path
from PIL import Image, ImageOps


def main():
    root = Path(__file__).parent
    settings = json.loads((root / "data/game.json").read_text())["art"]
    output = root / "assets"
    output.mkdir(exist_ok=True)
    for source in sorted((root / "raw_art").glob("*.png")):
        with Image.open(source) as original:
            picture = original.convert("RGBA")
        size = tuple(value * settings["scale"] for value in picture.size)
        picture.resize(size, Image.Resampling.NEAREST).save(output / source.name)
        if source.stem == "gem":
            for name, colours in settings["gems"].items():
                gem = ImageOps.colorize(ImageOps.grayscale(picture),
                                       black=tuple(colours[0]), mid=tuple(colours[1]),
                                       white=tuple(colours[2])).convert("RGBA")
                gem.putalpha(picture.getchannel("A"))
                gem.resize(size, Image.Resampling.NEAREST).save(output / f"{name}.png")
    print("Created 3x nearest-neighbour pictures and blue/pink gems in assets/.")


if __name__ == "__main__":
    main()
