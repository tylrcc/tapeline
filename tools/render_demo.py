"""render the 'see it run' terminal demo.

draws an animated terminal of `make sim` going green and writes docs/demo.gif
(for the readme) and docs/demo.mp4 (a short video). the lines below are the real
output of the testbench, just laid out for a clean recording. regenerate with:

    python3 tools/render_demo.py

needs Pillow. the mp4 step needs ffmpeg on PATH (it is skipped if missing).
"""

import os
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

# ---- look ----------------------------------------------------------------
W, H = 900, 380
FPS = 20
MARGIN_X = 26
TITLE_H = 40
TOP_PAD = 12
LINE_H = 24
FONT_SIZE = 15

BG      = (11, 15, 20)
TITLE   = (22, 28, 36)
DOT_R   = (255, 95, 86)
DOT_Y   = (255, 189, 46)
DOT_G   = (39, 201, 63)
FG      = (216, 222, 228)
DIM     = (108, 122, 136)
CYAN    = (54, 194, 224)
GREEN   = (61, 220, 151)
BRIGHT  = (236, 241, 246)

FONT_PATHS = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/SFNSMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]


def load_font(size):
    for p in FONT_PATHS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


FONT = load_font(FONT_SIZE)

# prompt shown before the command and at the end
PROMPT = [("~/tapeline", CYAN), (" $ ", DIM)]
CMD = "make sim"
DASH = "-" * 47

# the output, one entry per line: list of (text, color) spans
OUTPUT = [
    [("python3 sim/gen_vectors.py", DIM)],
    [("wrote 4000 vectors (3937 valid) -> sim/vectors.txt", CYAN)],
    [("mkdir -p build", DIM)],
    [("iverilog -g2012 -Wall -o build/mac_engine_tb.vvp \\", DIM)],
    [("    rtl/mac_engine.v rtl/tick_sync_fifo.v tb/mac_engine_tb.v", DIM)],
    [("vvp build/mac_engine_tb.vvp", DIM)],
    [(DASH, DIM)],
    [("mac_engine_tb: 4000 ticks, 3937 checked, ", FG), ("0 errors", GREEN)],
    [("PASS", GREEN)],
    [(DASH, DIM)],
]
BOLD_LINES = {8}  # render PASS heavier


def base_frame():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, TITLE_H], fill=TITLE)
    for i, c in enumerate((DOT_R, DOT_Y, DOT_G)):
        cx = 22 + i * 22
        d.ellipse([cx - 6, TITLE_H // 2 - 6, cx + 6, TITLE_H // 2 + 6], fill=c)
    title = "make sim  -  tapeline"
    tw = d.textlength(title, font=FONT)
    d.text(((W - tw) / 2, TITLE_H / 2 - FONT_SIZE / 2), title, font=FONT, fill=DIM)
    return img


def draw_line(d, y, spans, bold=False):
    x = MARGIN_X
    for text, color in spans:
        d.text((x, y), text, font=FONT, fill=color)
        if bold:
            d.text((x + 1, y), text, font=FONT, fill=color)  # fake-bold
        x += d.textlength(text, font=FONT)
    return x


def render(typed_cmd, n_output, cursor=False, cursor_on=True):
    """one still: command line typed to `typed_cmd`, `n_output` output lines shown."""
    img = base_frame()
    d = ImageDraw.Draw(img)
    y = TITLE_H + TOP_PAD

    # command line
    x = draw_line(d, y, PROMPT + [(typed_cmd, BRIGHT)])
    if n_output == 0 and cursor and cursor_on:
        d.rectangle([x + 1, y + 2, x + 9, y + FONT_SIZE + 4], fill=BRIGHT)
    y += LINE_H

    # output lines
    for i in range(n_output):
        draw_line(d, y, OUTPUT[i], bold=(i in BOLD_LINES))
        y += LINE_H

    # trailing prompt with blinking cursor once everything has printed
    if n_output >= len(OUTPUT):
        y += LINE_H // 2
        x = draw_line(d, y, PROMPT)
        if cursor_on:
            d.rectangle([x + 1, y + 2, x + 9, y + FONT_SIZE + 4], fill=BRIGHT)

    return img


def build_frames():
    frames = []

    def hold(img, seconds):
        for _ in range(max(1, int(seconds * FPS))):
            frames.append(img)

    # 1) empty prompt, blink the cursor a bit
    for _ in range(2):
        hold(render("", 0, cursor=True, cursor_on=True), 0.25)
        hold(render("", 0, cursor=True, cursor_on=False), 0.25)

    # 2) type the command
    for i in range(1, len(CMD) + 1):
        hold(render(CMD[:i], 0, cursor=True, cursor_on=True), 0.07)
    hold(render(CMD, 0, cursor=True, cursor_on=True), 0.45)

    # 3) stream the output, line by line
    for n in range(1, len(OUTPUT) + 1):
        # linger a touch longer on the result block
        secs = 0.32 if n in (8, 9) else 0.2
        hold(render(CMD, n), secs)

    # 4) final frame, blink the prompt cursor for a couple seconds
    for _ in range(3):
        hold(render(CMD, len(OUTPUT), cursor_on=True), 0.45)
        hold(render(CMD, len(OUTPUT), cursor_on=False), 0.4)
    hold(render(CMD, len(OUTPUT), cursor_on=True), 0.6)

    return frames


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs = os.path.join(here, "docs")
    os.makedirs(docs, exist_ok=True)
    gif_path = os.path.join(docs, "demo.gif")
    mp4_path = os.path.join(docs, "demo.mp4")

    frames = build_frames()
    dur_ms = int(1000 / FPS)

    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=dur_ms,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print("wrote %s (%d frames)" % (gif_path, len(frames)))

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg not found, skipping mp4")
        return

    tmp = tempfile.mkdtemp(prefix="tapeline_demo_")
    try:
        for i, f in enumerate(frames):
            f.save(os.path.join(tmp, "f%05d.png" % i))
        subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-framerate", str(FPS),
             "-i", os.path.join(tmp, "f%05d.png"),
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4_path],
            check=True,
        )
        print("wrote %s" % mp4_path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
