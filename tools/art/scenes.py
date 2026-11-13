"""The start screen's three card scenes (v31): each card's scene at desktop width and at 390 px, and a strip of frames
across its loop, for comparing builds.

    python tools/art/scenes.py --tag after            # tools/.build/shots/art/scenes_after_*.png
    python tools/art/scenes.py --tag before --frames 8
    python tools/art/scenes.py --video                # also an MP4 of each card's camera move (ffmpeg)

Each card is captured on its own (the canvas element), at 2x. The strip is a frame every loop/frames seconds of the
card's scene, side by side, in rows of four.
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import game_html, write_build, BUILD, launch
from playwright.sync_api import sync_playwright

OUT = os.path.join(BUILD, 'shots', 'art'); os.makedirs(OUT, exist_ok=True)
ap = argparse.ArgumentParser()
ap.add_argument('--tag', default='after'); ap.add_argument('--frames', type=int, default=8)
ap.add_argument('--span', type=float, default=0, help='seconds the strip covers (default: one camera period, three loops)')
ap.add_argument('--video', action='store_true', help='also record each card for one camera period (12 frames a second, ffmpeg)')
args = ap.parse_args()
PAGE = write_build('scenes.html', game_html())

def cards(pg):
    return pg.evaluate('() => [...document.querySelectorAll("#mode-cards .mcard")].map(c => !!c.querySelector("canvas.mart-live"))')

def shoot(pg, name, k):
    el = pg.query_selector_all('#mode-cards .mcard')[k]
    cv = el.query_selector('canvas.mart-live') or el.query_selector('svg.mart')
    cv.scroll_into_view_if_needed(); pg.wait_for_timeout(500)
    cv.screenshot(path=name)

with sync_playwright() as p:
    b = launch(p)
    errs = []
    for label, vp in (('desk', {'width': 1440, 'height': 900}), ('phone', {'width': 390, 'height': 844})):
        ctx = b.new_context(viewport=vp, device_scale_factor=2); pg = ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
        pg.goto('file://' + PAGE); pg.wait_for_timeout(600); pg.click('#info-go'); pg.wait_for_timeout(1500)
        live = cards(pg)
        for k in range(3):
            shoot(pg, f'{OUT}/scenes_{args.tag}_{label}_{k + 1}.png', k)
        ctx.close()
    # frame strips, desktop: a frame every span/frames seconds of each card
    from PIL import Image
    ctx = b.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=2); pg = ctx.new_page()
    pg.goto('file://' + PAGE); pg.wait_for_timeout(600); pg.click('#info-go'); pg.wait_for_timeout(1500)
    loops = [5, 4.6, 4.8]
    for k in range(3):
        span = args.span or loops[k] * 3  # one camera move: three loops of the scene
        el = pg.query_selector_all('#mode-cards .mcard')[k].query_selector('canvas.mart-live')
        if not el: continue
        shots = []
        for j in range(args.frames):
            f = f'{OUT}/_strip_{k}_{j}.png'; el.screenshot(path=f); shots.append(Image.open(f)); pg.wait_for_timeout(int(span * 1000 / args.frames))
        w, h = shots[0].size; cols = 4; rows = (len(shots) + cols - 1) // cols
        sheet = Image.new('RGB', (w * cols + 8 * (cols - 1), h * rows + 8 * (rows - 1)), (5, 7, 10))
        for j, im in enumerate(shots): sheet.paste(im, ((j % cols) * (w + 8), (j // cols) * (h + 8)))
        sheet.save(f'{OUT}/scenes_{args.tag}_strip_{k + 1}.png')
        for j in range(len(shots)): os.remove(f'{OUT}/_strip_{k}_{j}.png')
    if args.video:
        import base64, shutil, subprocess, tempfile
        for k in range(3):
            span = loops[k] * 3
            el = pg.query_selector_all('#mode-cards .mcard')[k]; el.scroll_into_view_if_needed(); pg.wait_for_timeout(300)
            frames = pg.evaluate('''([k, ms]) => new Promise(res => { const cv = document.querySelectorAll('#mode-cards .mcard')[k].querySelector('canvas.mart-live'), out = [], t0 = performance.now();
              const id = setInterval(() => { out.push(cv.toDataURL('image/jpeg', 0.9)); if (performance.now() - t0 > ms) { clearInterval(id); res(out); } }, 1000 / 12); })''', [k, int(span * 1000)])
            tmp = tempfile.mkdtemp()
            for j, d in enumerate(frames): open(f'{tmp}/f{j:04d}.jpg', 'wb').write(base64.b64decode(d.split(',', 1)[1]))
            out = f'{OUT}/scenes_{args.tag}_{k + 1}.mp4'
            # played back in real time, however many frames the page managed
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', f'{len(frames) / span:.3f}', '-i', f'{tmp}/f%04d.jpg', '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-pix_fmt', 'yuv420p', '-c:v', 'libx264', '-crf', '20', out], check=True)
            shutil.rmtree(tmp)
    ctx.close(); b.close()
    print(f'scenes in {OUT} (scenes_{args.tag}_*); errors: {errs[:5]}')
