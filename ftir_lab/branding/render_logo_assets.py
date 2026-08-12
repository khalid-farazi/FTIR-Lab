"""Render transparent PNG and animated GIF companions for the SVG logo."""
from __future__ import annotations

from pathlib import Path
import math

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
WIDTH, HEIGHT = 1000, 320
SCALE = 2
CENTER = (230.0, 160.0)
NAVY = (6, 19, 47, 255)
MAROON = (138, 21, 56, 255)
COLORS = [(17, 165, 121, 255), (59, 167, 216, 255),
          (138, 21, 56, 255), (233, 162, 59, 255)]

BASE = [(230, 160), (202, 137), (196, 91), (214, 62),
        (230, 42), (251, 80), (263, 126), (230, 160)]
TARGETS = [
    [(170, 80), (195, 80), (195, 110), (195, 160),
     (170, 160), (170, 120), (170, 90), (170, 80)],
    [(265, 80), (290, 80), (290, 110), (290, 160),
     (265, 160), (265, 120), (265, 90), (265, 80)],
    [(170, 160), (195, 160), (195, 190), (195, 240),
     (170, 240), (170, 210), (170, 180), (170, 160)],
    [(265, 160), (290, 160), (290, 190), (290, 240),
     (265, 240), (265, 210), (265, 180), (265, 160)],
]


def ease_out_quint(t):
    return 1 - (1 - t) ** 5


def ease_in_out(t):
    return 4*t*t*t if t < .5 else 1 - (-2*t + 2) ** 3 / 2


def lerp(a, b, t):
    return a + (b-a)*t


def rotate(points, degrees):
    angle = math.radians(degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    cx, cy = CENTER
    return [(cx + (x-cx)*cosine - (y-cy)*sine,
             cy + (x-cx)*sine + (y-cy)*cosine) for x, y in points]


def mix_points(a, b, t):
    return [(lerp(x1, x2, t), lerp(y1, y2, t))
            for (x1, y1), (x2, y2) in zip(a, b)]


def mix_color(a, b, t):
    return tuple(round(lerp(x, y, t)) for x, y in zip(a, b))


def scaled(points):
    return [(round(x*SCALE), round(y*SCALE)) for x, y in points]


def fonts():
    return (ImageFont.truetype(r"C:\Windows\Fonts\georgia.ttf", 78*SCALE),
            ImageFont.truetype(r"C:\Windows\Fonts\georgiab.ttf", 112*SCALE))


def draw_frame(time_s, static=False):
    image = Image.new("RGBA", (WIDTH*SCALE, HEIGHT*SCALE), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    spin_end, morph_end = 2.7, 3.85
    if static:
        spin, morph, reveal = 1440, 1, 1
    else:
        spin = 1440 * ease_out_quint(min(1, time_s/spin_end))
        morph = ease_in_out(max(0, min(1, (time_s-spin_end)/(morph_end-spin_end))))
        reveal = ease_in_out(max(0, min(1, (time_s-3.35)/.75)))

    for index in range(4):
        initial = rotate(BASE, spin + index*90)
        points = mix_points(initial, TARGETS[index], morph)
        draw.polygon(scaled(points), fill=mix_color(COLORS[index], NAVY, morph))

    hub_w, hub_h = lerp(22, 70, morph), lerp(22, 24, morph)
    x0, y0 = CENTER[0]-hub_w/2, CENTER[1]-hub_h/2
    draw.rounded_rectangle((round(x0*SCALE), round(y0*SCALE),
                            round((x0+hub_w)*SCALE), round((y0+hub_h)*SCALE)),
                           radius=round(lerp(11, 5, morph)*SCALE), fill=MAROON)

    if reveal:
        layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        word = ImageDraw.Draw(layer)
        regular, bold = fonts()
        shift = round((1-reveal)*24*SCALE)
        alpha = round(255*reveal)
        navy = NAVY[:3] + (alpha,)
        maroon = MAROON[:3] + (alpha,)
        word.text((310*SCALE+shift, 220*SCALE), "alal", font=regular,
                  fill=navy, anchor="ls")
        word.text((475*SCALE+shift, 220*SCALE), "FTIR", font=bold,
                  fill=navy, anchor="ls")
        word.rounded_rectangle((478*SCALE+shift, 237*SCALE,
                                764*SCALE+shift, 242*SCALE),
                               radius=3*SCALE, fill=maroon)
        image.alpha_composite(layer)
    return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def main():
    draw_frame(5, static=True).save(HERE / "halal_ftir_logo_static.png")
    fps, duration = 24, 5.2
    frames = [draw_frame(index/fps) for index in range(round(fps*duration))]
    # Hold the completed identity before the animation loops.
    frames.extend([draw_frame(duration)] * 18)
    frames[0].save(HERE / "halal_ftir_logo_animated.gif", save_all=True,
                   append_images=frames[1:], duration=round(1000/fps), loop=0,
                   disposal=2, optimize=True, transparency=0)


if __name__ == "__main__":
    main()
