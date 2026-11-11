"""The start screen's drawings (v25): the hero's board and the three mode cards, in the board's own drawing language
(slate walls joined by links, hairline towers with a turret and a dashed range ring, units in the army colours, the gold
keep), animated with SMIL. Their styles live in index.html (.st-scene, .mart, .tw, .un, .kp).

    python tools/art/start_art.py           # prints the four SVGs as JSON
    python tools/art/start_art.py --write   # puts them into index.html in place of the current ones
"""
import json, math, os, sys
C = 20  # cell size
COLS_ = ['#ffb547', '#e5472b', '#ff7b36', '#ff6fa8']

def wall_col(x, rows):
    out = []
    for r in rows:
        y = r * C + 10
        out.append(f'<rect x="{x-8}" y="{y-8}" width="16" height="16" rx="1.5"/>')
        if r + 1 in rows: out.append(f'<rect x="{x-3}" y="{y+7}" width="6" height="6"/>')
    return out

def tower(x, y, ang, sweep, k, rng=56):
    a0, a1 = ang - sweep, ang + sweep
    return (f'<g class="tw"><circle class="rg" cx="{x}" cy="{y}" r="{rng}"/>'
            f'<rect class="tb" x="{x-8.5}" y="{y-8.5}" width="17" height="17"/>'
            f'<g transform="translate({x} {y})"><g><animateTransform attributeName="transform" type="rotate" values="{a0};{a1};{a0}" dur="{4+k%3}s" repeatCount="indefinite" begin="-{k*0.7:.1f}s"/>'
            f'<rect class="tt" x="1" y="-1.6" width="9.5" height="3.2"/><circle class="tc" r="3.6"/><circle class="td" r="1"/></g></g></g>')

def hero():
    W, H = 1200, 240
    rows = list(range(12))
    cols = [170 + 120 * k for k in range(8)]
    walls = []
    for k, x in enumerate(cols):
        walls += wall_col(x, list(range(3, 12)) if k % 2 == 0 else list(range(0, 9)))
    # route through cell centres
    pts = [(-30, 130), (110, 130)]
    xs = [110 + 120 * k for k in range(9)]
    for k in range(8):
        y = 30 if k % 2 == 0 else 210
        pts += [(xs[k], y), (xs[k + 1], y)]
    pts += [(1070, 130), (1150, 130)]
    d = 'M' + ' L'.join(f'{x} {y}' for x, y in pts)
    L = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    # towers on wall cells next to the route's turns
    tws = [(170, 70, -100, 35), (290, 170, 100, 35), (410, 130, -60, 50), (530, 170, 90, 40), (650, 70, -90, 40), (770, 110, 130, 45), (890, 70, -110, 35), (1010, 170, 80, 40)]
    towers = ''.join(tower(x, y, a, s, k) for k, (x, y, a, s) in enumerate(tws))
    # tracers from a few towers to the route beside them
    tr = []
    for k, (x, y, x2, y2, dur, beg) in enumerate([(170, 70, 120, 32, 1.3, .2), (410, 130, 470, 150, 1.7, .9), (650, 70, 600, 40, 1.1, .4), (770, 110, 830, 160, 1.5, 1.2), (1010, 170, 1068, 190, 1.9, .6), (290, 170, 345, 205, 1.4, 1.0)]):
        tr.append(f'<line class="trc" x1="{x}" y1="{y}" x2="{x2}" y2="{y2}"><animate attributeName="opacity" values="0;0;1;0" keyTimes="0;.78;.82;1" dur="{dur}s" begin="{beg}s" repeatCount="indefinite"/></line>')
    # terrain: rough (stippled) and rock (hatched)
    rough = ''.join(f'<rect class="rf" x="{x-10}" y="{y-10}" width="20" height="20"/>' for x, y in [(330, 110), (330, 130), (690, 150), (690, 170), (950, 110)])
    rock = ''.join(f'<rect class="rk" x="{x-9}" y="{y-9}" width="18" height="18" rx="2"/>' for x, y in [(50, 210), (70, 210), (1130, 30), (1150, 30)])
    # units: army colours, a big one, a sapper
    speed = 64
    dur = L / speed
    units = []
    n = 12
    for i in range(n):
        beg = -(i * dur / n)
        col = COLS_[i % 4]
        if i == 5:
            body = f'<path class="sp" d="M0 -7 L7 0 L0 7 L-7 0Z" stroke="{COLS_[2]}"/><path class="spi" d="M-3 -1.5 H3 M-3 1.5 H3" stroke="{COLS_[2]}"/>'
        elif i % 4 == 1:
            body = f'<circle r="7.2" fill="{col}"/><circle r="7.2" class="ud"/>'
        else:
            body = f'<circle r="5" fill="{col}"/><circle r="5" class="ud"/>'
        units.append(f'<g class="un">{body}<animateMotion dur="{dur:.1f}s" repeatCount="indefinite" begin="{beg:.2f}s"><mpath href="#st-route"/></animateMotion></g>')
    keep = ('<g class="kp" transform="translate(1166 130)"><rect class="kpr" x="-17" y="-17" width="34" height="34" rx="2"><animate attributeName="opacity" values=".7;0" dur="2.4s" repeatCount="indefinite"/>'
            '<animateTransform attributeName="transform" type="scale" values="1;1.7" dur="2.4s" repeatCount="indefinite"/></rect>'
            '<rect class="kpb" x="-12" y="-12" width="24" height="24" rx="2"/><path class="kpd" d="M0 -6 L6 0 L0 6 L-6 0Z"/></g>')
    svg = (f'<svg class="st-scene" viewBox="0 0 {W} {H}" preserveAspectRatio="xMaxYMid slice" aria-hidden="true" focusable="false">'
           '<defs><pattern id="st-dots" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="0" cy="0" r="1" fill="rgba(150,172,190,.24)"/></pattern>'
           '<pattern id="st-stip" width="5" height="5" patternUnits="userSpaceOnUse"><circle cx="2.5" cy="2.5" r=".8" fill="rgba(190,170,140,.35)"/></pattern>'
           '<pattern id="st-hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="1.4" height="5" fill="rgba(150,172,190,.28)"/></pattern>'
           f'<path id="st-route" d="{d}"/></defs>'
           f'<rect x="-2400" y="-400" width="{W + 4800}" height="{H + 800}" fill="url(#st-dots)"/>'  # past the edges: where the hero is wider than the drawing, the dots still run to its ends
           f'<g>{rough}</g><g>{rock}</g>'
           f'<path class="rt" d="{d}"/><path class="rt2" d="{d}"/>'
           f'<g class="wl">{"".join(walls)}</g>'
           f'{towers}{"".join(tr)}{keep}{"".join(units)}</svg>')
    return svg, L, dur

def card_solo():
    # the computer (a chip) sends its army along the route; a tower holds the line
    pins = ''.join(f'<path d="M{x} 44 v-7 M{x} 96 v7"/>' for x in (58, 70, 82)) + ''.join(f'<path d="M48 {y} h-7 M92 {y} h7"/>' for y in (58, 70, 82))
    units = ''.join(f'<g class="un"><circle r="{5.5 if i % 3 else 7}" fill="{COLS_[i % 4]}"/><circle r="{5.5 if i % 3 else 7}" class="ud"/><animateMotion dur="8s" repeatCount="indefinite" begin="-{i*1.6:.2f}s" path="M100 70 H700"/><animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.04;.5;.62" dur="8s" repeatCount="indefinite" begin="-{i*1.6:.2f}s"/></g>' for i in range(5))
    return ('<svg class="mart" viewBox="0 0 360 130" preserveAspectRatio="xMidYMid meet" aria-hidden="true" focusable="false">'
            '<g transform="translate(180 65) scale(.9) translate(-150 -70)">'
            '<path class="rt" d="M100 70 H700"/>'
            f'<g class="chip"><rect x="48" y="44" width="44" height="52" rx="6"/><g class="pins">{pins}</g>'
            '<rect class="core" x="60" y="60" width="20" height="20" rx="2"><animate attributeName="opacity" values=".35;1;.35" dur="2.2s" repeatCount="indefinite"/></rect>'
            '<path class="eye" d="M64 67 h4 M72 67 h4"/></g>'
            '<g class="wl"><rect x="212" y="26" width="16" height="16" rx="1.5"/><rect x="232" y="26" width="16" height="16" rx="1.5"/><rect x="227" y="31" width="6" height="6"/>'
            '<rect x="212" y="98" width="16" height="16" rx="1.5"/><rect x="192" y="98" width="16" height="16" rx="1.5"/><rect x="207" y="103" width="6" height="6"/></g>'
            + tower(200, 34, 70, 30, 1, 52) + tower(240, 106, -80, 30, 2, 52) +
            '<line class="trc" x1="200" y1="34" x2="214" y2="66"><animate attributeName="opacity" values="0;0;1;0" keyTimes="0;.7;.76;1" dur="1.1s" repeatCount="indefinite"/></line>'
            '<line class="trc" x1="240" y1="106" x2="252" y2="74"><animate attributeName="opacity" values="0;0;1;0" keyTimes="0;.7;.76;1" dur="1.4s" begin=".5s" repeatCount="indefinite"/></line>'
            f'{units}</g></svg>')

def mini_board(x, y, w, h, side):
    """A tiny board on a device screen: a tower (defender) or a few units (attacker)."""
    out = [f'<rect class="scr {side}" x="{x}" y="{y}" width="{w}" height="{h}" rx="3"/>']
    cx, cy = x + w / 2, y + h / 2
    if side == 'def':
        out.append(f'<rect class="tb" x="{cx-7}" y="{cy-7}" width="14" height="14"/><circle class="tc" cx="{cx}" cy="{cy}" r="3"/><circle class="rg" cx="{cx}" cy="{cy}" r="{min(w,h)*0.38:.0f}"/>')
    else:
        for i, (dx, dy) in enumerate([(-9, 4), (0, -5), (9, 3), (-2, 10)]):
            out.append(f'<circle cx="{cx+dx}" cy="{cy+dy}" r="3.4" fill="{COLS_[i%4]}"/>')
    return ''.join(out)

def card_local():
    # one device, both sides: pass it across
    return ('<svg class="mart" viewBox="0 0 360 130" preserveAspectRatio="xMidYMid meet" aria-hidden="true" focusable="false">'
            '<g transform="translate(180 65) scale(.9) translate(-150 -70)">'
            '<rect class="dev" x="84" y="30" width="132" height="84" rx="10"/>'
            '<clipPath id="mc-scr"><rect x="94" y="38" width="112" height="68" rx="3"/></clipPath>'
            '<g clip-path="url(#mc-scr)"><rect class="half def" x="94" y="38" width="56" height="68"><animate attributeName="opacity" values="1;1;.35;.35;1" keyTimes="0;.42;.5;.92;1" dur="5s" repeatCount="indefinite"/></rect>'
            '<rect class="half atk" x="150" y="38" width="56" height="68"><animate attributeName="opacity" values=".35;.35;1;1;.35" keyTimes="0;.42;.5;.92;1" dur="5s" repeatCount="indefinite"/></rect>'
            '<path class="seam" d="M150 38 V106"/>'
            '<rect class="tb" x="114" y="64" width="14" height="14"/><circle class="tc" cx="121" cy="71" r="3"/>'
            + ''.join(f'<circle cx="{x}" cy="{y}" r="3.4" fill="{COLS_[i%4]}"/>' for i, (x, y) in enumerate([(168, 62), (180, 72), (172, 84), (190, 60)])) +
            '</g><circle class="cam" cx="150" cy="34" r="1.3"/>'
            '<path class="swap" d="M70 66 C 70 22, 120 12, 150 14"/><path class="swaph" d="M146 9 L152 14 L146 19"/>'
            '<path class="swap atk" d="M230 78 C 230 122, 180 132, 150 130"/><path class="swaph atk" d="M154 125 L148 130 L154 135"/>'
            '</g></svg>')

def card_online():
    # two devices, one link
    arc = 'M100 44 C 120 6, 180 6, 200 44'
    return ('<svg class="mart" viewBox="0 0 360 130" preserveAspectRatio="xMidYMid meet" aria-hidden="true" focusable="false">'
            '<g transform="translate(180 65) scale(.9) translate(-150 -70)">'
            '<rect class="dev def" x="52" y="40" width="50" height="86" rx="9"/>' + mini_board(58, 50, 38, 64, 'def') +
            '<rect class="dev atk" x="198" y="40" width="50" height="86" rx="9"/>' + mini_board(204, 50, 38, 64, 'atk') +
            f'<path class="link" d="{arc}"/>'
            f'<circle class="pkt" r="3.4"><animateMotion dur="2.6s" repeatCount="indefinite" path="{arc}" keyPoints="0;1;0" keyTimes="0;.5;1" calcMode="linear"/>'
            '<animate attributeName="fill" values="#4fd6ee;#4fd6ee;#ff8a3d;#ff8a3d;#4fd6ee" keyTimes="0;.45;.5;.95;1" dur="2.6s" repeatCount="indefinite"/></circle>'
            '<path class="wave def" d="M70 30 q7 -7 14 0 M66 24 q11 -11 22 0"><animate attributeName="opacity" values=".2;1;.2" dur="1.3s" repeatCount="indefinite"/></path>'
            '<path class="wave atk" d="M216 30 q7 -7 14 0 M212 24 q11 -11 22 0"><animate attributeName="opacity" values=".2;1;.2" dur="1.3s" begin=".65s" repeatCount="indefinite"/></path>'
            '</g></svg>')

def write(art):
    """Swaps each drawing in index.html: the hero's svg.st-scene, and the svg.mart in each card (found by its title id)."""
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'index.html')
    s = open(p, encoding='utf-8').read()
    a = s.index('<svg class="st-scene"'); b = s.index('<div class="st-brand">', a)
    s = s[:a] + art['hero'] + '\n      ' + s[b:]
    for key, label in (('solo', 'mc-solo'), ('local', 'mc-local'), ('online', 'mc-online')):
        i = s.index(f'aria-labelledby="{label}">'); a = s.index('<svg class="mart"', i); b = s.index('<div class="mhead">', a)
        s = s[:a] + art[key] + '\n        ' + s[b:]
    open(p, 'w', encoding='utf-8').write(s)

if __name__ == '__main__':
    h, L, dur = hero()
    art = {'hero': h, 'solo': card_solo(), 'local': card_local(), 'online': card_online()}
    if '--write' in sys.argv: write(art); print(f'index.html updated (route {L:.0f} px, a unit takes {dur:.1f} s)')
    else: print(json.dumps(art))
