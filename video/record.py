"""Frame-accurate recording of stage.html: virtual clock, scripted pointer, scripted camera, piped to ffmpeg."""
import argparse, base64, math, os, pathlib, subprocess, sys, time
import cv2, numpy as np
from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument('--out', default='out.mp4')
ap.add_argument('--dsf', type=float, default=3.6)
ap.add_argument('--w', type=int, default=1920)
ap.add_argument('--skip', type=int, default=1)       # capture every n-th 60 Hz step
ap.add_argument('--t0', type=float, default=0)
ap.add_argument('--t1', type=float, default=None)
ap.add_argument('--stills', default='')              # comma list of times: dump PNGs instead of a video
A = ap.parse_args()
W, H = A.w, A.w * 9 // 16
FPS = 60
VW, VH = 1600, 900            # page viewport (stage is the centred 1280x720)

ease = lambda u: u * u * u * (u * (6 * u - 15) + 10)
def track(keys, t):
    """keys: [(t, v...)] -> eased value at t (holds outside)."""
    if t <= keys[0][0]: return keys[0][1:]
    for a, b in zip(keys, keys[1:]):
        if t <= b[0]:
            u = ease((t - a[0]) / (b[0] - a[0])) if b[0] > a[0] else 1
            return tuple(p + (q - p) * u for p, q in zip(a[1:], b[1:])), (a, b, u)
    return keys[-1][1:]

HERE = pathlib.Path(__file__).resolve().parent
chrome = os.environ.get('CHROME_PATH') or None      # default: Playwright's own Chromium
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=chrome, headless=True, args=['--force-color-profile=srgb', '--font-render-hinting=none'])
    pg = b.new_page(viewport={'width': VW, 'height': VH}, device_scale_factor=A.dsf, color_scheme='dark')
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.goto((HERE / 'stage.html').as_uri())
    cdp = pg.context.new_cdp_session(pg)

    def box(sel):
        return pg.evaluate("s=>{const r=document.querySelector(s).getBoundingClientRect();return [r.x,r.y,r.width,r.height]}", sel)
    def ctr(sel, dx=0, dy=0):
        x, y, w, h = box(sel); return (x + w / 2 + dx, y + h / 2 + dy)
    def span(*sels):
        bs = [box(s) for s in sels]
        x0 = min(q[0] for q in bs); y0 = min(q[1] for q in bs); x1 = max(q[0] + q[2] for q in bs); y1 = max(q[1] + q[3] for q in bs)
        return ((x0 + x1) / 2, (y0 + y1) / 2)

    x, y = VW / 2 + 150, 420
    pg.mouse.move(x, y)
    for _ in range(90): pg.evaluate(f'__step({1000 / FPS}, {x}, {y}, false)')     # settle before measuring

    SW = ctr('#theme'); KN = ctr('#theme .knob'); KR = (2 * SW[0] - KN[0], KN[1])
    B1 = ctr('#b1'); B2 = ctr('#b2'); PL = ctr('#play'); BT = span('#b1', '#play')
    SL = span('#slider', '#readout'); sx, sy, sw, sh = box('#slider input')
    knob = lambda v: (sx + 18 + v / 100 * (sw - 36), sy + sh / 2 + 3)
    CARD = ctr('#card'); S2 = ctr('#seg label:nth-of-type(2)'); S3 = ctr('#seg label:nth-of-type(3)')
    FD = ctr('#field'); C2 = ctr('.check:nth-of-type(2) .box'); CK = span('.check:nth-of-type(1)', '.check:nth-of-type(2)')
    WIDE = (VW / 2, VH / 2, 1.0)
    TEXT = '少即是多，把光和暗留下'
    Z = 2.4

    # ---- storyboard ---------------------------------------------------------
    CAM, CUR, EV = [], [], []
    cam = lambda t, cx, cy, z: CAM.append((t, cx, cy, z))
    cur = lambda t, p, dx=0, dy=0: CUR.append((t, p[0] + dx, p[1] + dy))
    def click(t): EV.extend([(t, 'down'), (t + .1, 'up')])

    # A  the whole kit: one click turns the whole page light; then push in on the switch and flip it back
    cam(0, *WIDE); cam(3.7, *WIDE); cam(5.0, SW[0], SW[1] + 10, Z); cam(7.6, SW[0], SW[1] + 10, Z)
    cur(0, SW, 300, 230); cur(.5, SW, 300, 230); cur(1.5, KN, 10, 14); click(1.8); cur(3.6, KN, 10, 14)
    cur(4.8, KR, 6, 12); click(5.4); cur(6.5, KR, 6, 12); cur(7.0, KN, 14, 16); cur(7.6, KN, 14, 16)
    # B  straight down to the card: day / week / month
    t = 7.6
    cam(t + 1.3, CARD[0], CARD[1] + 10, Z); cam(t + 6.3, CARD[0], CARD[1] + 10, Z)
    cur(t + 1.2, CARD, -130, 70); cur(t + 1.9, CARD, -120, -60); cur(t + 2.4, S2, 6, 11); click(t + 2.5); cur(t + 3.7, S2, 6, 11)
    cur(t + 4.0, S3, 6, 11); click(t + 4.1); cur(t + 5.4, S3, 6, 11); cur(t + 6.3, CARD, 50, 55)
    # C  finale: back out, flip the whole page to light
    t += 6.3
    cam(t + 1.3, *WIDE); cam(t + 2.0, *WIDE); cam(t + 4.8, VW / 2, VH / 2, 1.06)
    cur(t + 1.4, KN, 10, 14); click(t + 1.8); cur(t + 2.3, KN, 10, 14); cur(t + 3.4, SW, 30, 150)
    TOTAL = t + 4.8
    EV.sort(key=lambda e: e[0])
    END = TOTAL if A.t1 is None else A.t1
    print(f'total {TOTAL:.1f}s', flush=True)
    # -------------------------------------------------------------------------

    def cursor(t):
        r = track(CUR, t)
        if len(r) == 2 and isinstance(r[1], tuple) and len(r[1]) == 3 and isinstance(r[1][0], tuple):
            (x, y), (a, b_, u) = r
            dx, dy = b_[1] - a[1], b_[2] - a[2]; d = math.hypot(dx, dy)
            if d > 60:                                   # bow long moves a little, like a wrist arc
                k = .05 * math.sin(math.pi * u); x += -dy * k; y += dx * k
            return x, y
        return r
    def camera(t):
        r = track(CAM, t)
        if isinstance(r[1], tuple): r = r[0]
        cx, cy, z = r
        vw, vh = 1280 / z, 720 / z
        cx = min(max(cx, vw / 2), VW - vw / 2); cy = min(max(cy, vh / 2), VH - vh / 2)
        return cx - vw / 2, cy - vh / 2, vw, vh

    def shoot(t):
        x0, y0, vw, vh = camera(t)
        cx0, cy0 = max(0, math.floor(x0) - 2), max(0, math.floor(y0) - 2)
        cx1, cy1 = min(VW, math.ceil(x0 + vw) + 2), min(VH, math.ceil(y0 + vh) + 2)
        r = cdp.send('Page.captureScreenshot', {'format': 'png', 'optimizeForSpeed': True,
                     'clip': {'x': cx0, 'y': cy0, 'width': cx1 - cx0, 'height': cy1 - cy0, 'scale': A.dsf}})
        img = cv2.imdecode(np.frombuffer(base64.b64decode(r['data']), np.uint8), cv2.IMREAD_COLOR)
        k = img.shape[1] / (cx1 - cx0)                   # device px per css px
        if A.stills: print('clip', cx1 - cx0, cy1 - cy0, 'img', img.shape, 'k', round(k, 3), flush=True)
        S = 2                                            # supersample, then box down
        f = vw * k / (W * S)                             # src px per dst px
        M = np.float32([[f, 0, (x0 - cx0) * k + (f - 1) / 2], [0, f, (y0 - cy0) * k + (f - 1) / 2]])
        big = cv2.warpAffine(img, M, (W * S, H * S), flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
        return cv2.resize(big, (W, H), interpolation=cv2.INTER_AREA)

    stills = [float(v) for v in A.stills.split(',')] if A.stills else None
    ff = None
    if not stills:
        ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS / A.skip), '-i', '-',
                               '-vf', 'format=yuv420p', '-c:v', 'libx264', '-preset', 'slow', '-crf', '15', '-x264-params', 'aq-mode=3',
                               '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-movflags', '+faststart', A.out], stdin=subprocess.PIPE)

    x, y = cursor(0); pg.mouse.move(x, y)
    for _ in range(30): pg.evaluate(f'__step({1000 / FPS}, {x}, {y}, false)')
    down = False; ei = 0; n = round(END * FPS); t_start = time.time(); shot = 0
    for i in range(n + 1):
        t = i / FPS
        nx, ny = cursor(t)
        if (nx, ny) != (x, y): x, y = nx, ny; pg.mouse.move(x, y)
        while ei < len(EV) and EV[ei][0] <= t + 1e-9:
            e = EV[ei]; ei += 1
            if e[1] == 'down': pg.mouse.down(); down = True
            elif e[1] == 'up': pg.mouse.up(); down = False
            elif e[1] == 'type': pg.keyboard.insert_text(e[2])
        pg.evaluate(f'__step({1000 / FPS}, {x}, {y}, {"true" if down else "false"})')
        if t < A.t0: continue
        if stills:
            if any(abs(t - s) < .5 / FPS for s in stills):
                cv2.imwrite(f'still_{t:05.2f}.png', shoot(t))
            continue
        if i % A.skip: continue
        ff.stdin.write(shoot(t).tobytes()); shot += 1
        if shot % 120 == 0: print(f't={t:.1f}s  {shot} frames  {(time.time() - t_start) / shot:.2f}s/frame', flush=True)
    if ff: ff.stdin.close(); ff.wait()
    print('errors:', errs)
    print('state:', pg.evaluate("[document.documentElement.dataset.theme, document.querySelector('#slider input').value, document.querySelector('#play').getAttribute('aria-pressed'), document.querySelector('#field input').value, document.querySelector('input[name=range]:checked').value, [...document.querySelectorAll('.check input')].map(c=>c.checked)]"))
    b.close()
