"""The synthesised sounds, rendered offline and measured (v32): for each sound in SOUNDS, through the game's own master
chain, its peak, loudness (RMS over its first 0.3 s), brightness (spectral centroid, and the share of energy above
3 kHz) and length (to -40 dB). Compare two builds: run it in each checkout. --wav writes each as a WAV to listen to.

    python tools/art/sounds.py                    # the table
    python tools/art/sounds.py --wav              # ... and tools/.build/sounds/<name>.wav
"""
import os, sys, json, argparse, wave, struct
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import game_html, write_build, launch, BUILD
from playwright.sync_api import sync_playwright
import numpy as np

ap = argparse.ArgumentParser(); ap.add_argument('--wav', action='store_true'); ap.add_argument('--names', default='blaster,gatling,rail,mortar,boom,zap,frost,venom,kill')
a = ap.parse_args()
HOOK = 'window.__snd = { SND, SOUNDS, get sndStart() { return sndStart; } };\n'
PAGE = write_build('sounds.html', game_html().replace('window.siegeline = {', HOOK + 'window.siegeline = {', 1))
JS = r'''async ([name, master]) => {
  const W = window.__snd, SR = 44100, ctx = new OfflineAudioContext(1, SR * 1.6, SR), real = W.SND.ctx;
  // the game's master chain, built the way sndStart builds it, on the offline context
  const AC = window.AudioContext; window.AudioContext = function () { return ctx; }; window.webkitAudioContext = undefined;
  const keep = { ...W.SND }; W.SND.ctx = null; W.SND.on = true;
  try { W.sndStart(); } finally { window.AudioContext = AC; }
  if (!master) { W.SND.out.disconnect(); W.SND.out.connect(ctx.destination); }
  Math.random = (() => { let s = 7; return () => { s = (s * 16807) % 2147483647; return s / 2147483647; }; })(); // the same each run
  W.SOUNDS[name][1]({ r: 0.5, k: 0.5 });
  const buf = await ctx.startRendering();
  Object.assign(W.SND, keep);
  return Array.from(buf.getChannelData(0));
}'''
out = os.path.join(BUILD, 'sounds'); os.makedirs(out, exist_ok=True)
with sync_playwright() as p:
    b = launch(p); pg = b.new_page(); pg.goto('file://' + PAGE); pg.wait_for_timeout(400)
    print(f'{"sound":9s} {"peak":>6s} {"rms":>6s} {"A dB":>6s} {"centroid":>9s} {">3kHz":>6s} {"length":>7s}')
    for n in a.names.split(','):
        if not pg.evaluate('(n) => !!window.__snd.SOUNDS[n]', n): continue
        x = np.array(pg.evaluate(JS, [n, True]), dtype=float); SR = 44100
        peak = np.abs(x).max(); rms = np.sqrt(np.mean(x[:int(0.3 * SR)] ** 2))
        X = np.abs(np.fft.rfft(x)) ** 2; f = np.fft.rfftfreq(len(x), 1 / SR)
        cen = (X * f).sum() / max(X.sum(), 1e-12); hi = X[f > 3000].sum() / max(X.sum(), 1e-12)
        f2 = f ** 2; RA = (12194 ** 2 * f2 ** 2) / ((f2 + 20.6 ** 2) * np.sqrt((f2 + 107.7 ** 2) * (f2 + 737.9 ** 2)) * (f2 + 12194 ** 2) + 1e-30)
        adb = 10 * np.log10(max((X * (RA / RA.max()) ** 2).sum() / len(x) ** 2 * 2, 1e-20))  # A-weighted level (relative), for loudness as heard
        env = np.abs(x); idx = np.where(env > peak * 0.01)[0]; length = (idx[-1] / SR) if len(idx) else 0
        print(f'{n:9s} {peak:6.3f} {rms:6.3f} {adb:6.1f} {cen:8.0f}Hz {100 * hi:5.1f}% {length:6.2f}s')
        if a.wav:
            with wave.open(os.path.join(out, n + '.wav'), 'w') as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
                w.writeframes(b''.join(struct.pack('<h', int(max(-1, min(1, v)) * 32767)) for v in x))
    b.close()
