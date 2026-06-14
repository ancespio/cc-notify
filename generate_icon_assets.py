#!/usr/bin/env python
"""Generate deterministic Agents-Notify PNG and ICO assets."""

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
PNG_PATH = ROOT / "assets" / "agents-notify.png"
ICO_PATH = ROOT / "build" / "agents-notify.ico"
SIZE = 1024


def draw_icon(size: int = SIZE) -> Image.Image:
    scale = size / SIZE

    def box(values):
        return tuple(round(value * scale) for value in values)

    image = Image.new("RGBA", (size, size), "#FAFCF8")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        box((0, 0, 1023, 1023)),
        radius=round(82 * scale),
        fill="#FAFCF8",
    )

    charcoal = "#26312E"
    coral = "#F06F5F"
    white = "#FFFFFF"
    draw.ellipse(box((256, 158, 768, 702)), fill=charcoal)
    draw.rectangle(box((256, 430, 768, 646)), fill=charcoal)
    draw.polygon(
        [box((256, 646))[0:2], box((768, 646))[0:2],
         box((844, 748))[0:2], box((180, 748))[0:2]],
        fill=charcoal,
    )
    draw.arc(
        box((278, 182, 746, 676)),
        start=180,
        end=360,
        fill=charcoal,
        width=max(1, round(44 * scale)),
    )
    draw.polygon(
        [
            box((422, 804))[0:2],
            box((602, 804))[0:2],
            box((576, 858))[0:2],
            box((512, 886))[0:2],
            box((448, 858))[0:2],
        ],
        fill=charcoal,
    )
    width = max(1, round(48 * scale))
    draw.line(
        [box((388, 454))[0:2], box((500, 540))[0:2],
         box((388, 626))[0:2]],
        fill=white,
        width=width,
        joint="curve",
    )
    draw.line(
        [box((530, 632))[0:2], box((658, 632))[0:2]],
        fill=white,
        width=width,
    )
    draw.ellipse(box((706, 162, 858, 314)), fill=coral)
    return image


def generate() -> None:
    PNG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ICO_PATH.parent.mkdir(parents=True, exist_ok=True)
    image = draw_icon()
    image.save(PNG_PATH, format="PNG")
    image.save(
        ICO_PATH,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (256, 256)],
    )


if __name__ == "__main__":
    generate()
