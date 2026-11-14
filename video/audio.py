"""Synthesised soundtrack for light-kit-demo-v3: ambient pad that follows the theme, bell notes, UI clicks on the storyboard's click times."""
import numpy as np, wave, sys
from scipy.signal import fftconvolve, butter, sosfilt

SR = 48000
DUR = 18.717
N = int(SR * DUR)
rng = np.random.default_rng(7)
t_all = np.arange(N) / SR
midi = lambda m: 440 * 2 ** ((m - 69) / 12)

def place(buf, sig, t, gain=1.0, pan=0.0):
    """sig mono or stereo -> add into stereo buf at time t, equal-power pan."""
    i = int(round(t * SR))
    if sig.ndim == 1:
        a = (pan + 1) * np.pi / 4
        sig = np.stack([sig * np.cos(a), sig * np.sin(a)], 1)
    n = min(len(sig), len(buf) - i)
    if n > 0: buf[i:i + n] += sig[:n] * gain

def smooth(x, a, b):
    u = np.clip((x - a) / (b - a), 0, 1); return u * u * (3 - 2 * u)

# ---- pad ---------------------------------------------------------------------
def pad(notes, env, tilt):
    """Detuned additive pad; env is a per-sample gain curve; tilt = harmonic rolloff exponent."""
    out = np.zeros((N, 2))
    for m in notes:
        f0 = midi(m)
        for det in ((0,) if m < 50 else (-6, 0, 5)):             # cents; no detune in the bass (it beats and booms)
            f = f0 * 2 ** (det / 1200)
            ph = rng.uniform(0, 2 * np.pi)
            lfo = 1 + .18 * np.sin(2 * np.pi * rng.uniform(.07, .19) * t_all + rng.uniform(0, 6.28))
            s = np.zeros(N)
            for h in range(1, 9):
                if f * h > 2600: break
                s += np.sin(2 * np.pi * f * h * t_all + ph * h) / h ** tilt
            p = rng.uniform(-.7, .7); a = (p + 1) * np.pi / 4
            g = lfo * env * (.55 if m < 47 else .9 if m < 50 else 1.0)   # keep the bass light: phone speakers drop it anyway
            out[:, 0] += s * g * np.cos(a); out[:, 1] += s * g * np.sin(a)
    return out

DARK = [38, 45, 50, 53, 57, 60, 64]          # D2 A2 D3 F3 A3 C4 E4   (Dm9)
LITE = [41, 48, 53, 57, 60, 64, 67]          # F2 C3 F3 A3 C4 E4 G4   (Fmaj9)
ON1, OFF1, ON2 = 1.9, 5.5, 15.8              # theme flips (mouse-up)
lite = smooth(t_all, ON1, ON1 + .9) * (1 - smooth(t_all, OFF1, OFF1 + .9)) + smooth(t_all, ON2, ON2 + .9)
master = smooth(t_all, 0, 1.4) * (1 - smooth(t_all, DUR - 2.4, DUR - .05))
music = pad(DARK, (1 - lite) * master, 1.75) * .054 + pad(LITE, lite * master, 1.45) * .047
# sub that swells under the finale
music += (np.sin(2 * np.pi * midi(29) * t_all) * smooth(t_all, ON2, ON2 + 1.2) * master * .03)[:, None]

# ---- bell --------------------------------------------------------------------
def bell(m, dur=2.6, bright=.5):
    n = int(SR * dur); t = np.arange(n) / SR; f = midi(m)
    s = np.zeros(n)
    for ratio, amp, dec in ((1, 1, 1.0), (2, .45 * bright + .1, .55), (3.01, .28 * bright, .35), (4.2, .16 * bright, .22), (5.43, .08 * bright, .15)):
        s += amp * np.sin(2 * np.pi * f * ratio * t) * np.exp(-t / (dec * dur * .32))
    return s * np.minimum(1, t / .004)

wet = np.zeros((N, 2))                       # everything that goes through the reverb
def note(t, m, g=.5, pan=0.0, bright=.5): place(wet, bell(m, bright=bright), t, g * .16, pan)

# sparse line in dark
for t, m, g, p in ((.45, 62, .5, -.3), (1.15, 69, .4, .3),
                   (6.75, 65, .45, -.3), (7.45, 69, .4, .25), (8.35, 74, .5, -.2), (9.15, 76, .4, .3),
                   (10.95, 72, .4, -.3), (12.55, 76, .4, .3), (13.35, 74, .45, -.2), (14.35, 69, .45, .2)):
    note(t, m, g, p, .35)
# line in the first light
for t, m, g, p in ((3.1, 79, .4, .3), (3.95, 76, .4, -.3), (4.75, 72, .35, .2)):
    note(t, m, g, p, .7)
# theme flips: rising arpeggio into light, falling into dark
for i, m in enumerate((65, 69, 72, 76)): note(ON1 + .02 + i * .085, m, .75 - i * .05, -.45 + i * .3, .8)
for i, m in enumerate((76, 72, 69, 62)): note(OFF1 + .02 + i * .095, m, .6 - i * .05, .45 - i * .3, .3)
for i, m in enumerate((65, 69, 72, 76, 79, 81)): note(ON2 + .02 + i * .085, m, .85 - i * .05, -.5 + i * .2, .9)
note(ON2 + 1.25, 84, .4, .2, .8); note(ON2 + 1.9, 88, .3, -.2, .8)

# ---- particles regrouping (card: day -> week -> month) ------------------------
PENTA = [86, 88, 91, 93, 96, 98, 100, 103]
def sparkle(t0, rising=True, k=26, span=.55):
    for j in range(k):
        u = j / (k - 1)
        m = PENTA[int(np.clip((u if rising else 1 - u) * 7 + rng.normal(0, 1.2), 0, 7))]
        n = int(SR * .09); tt = np.arange(n) / SR
        s = np.sin(2 * np.pi * midi(m) * tt) * np.exp(-tt / .018) * np.minimum(1, tt / .001)
        place(wet, s, t0 + u ** 1.3 * span + rng.uniform(0, .02), .028 * (1 - .5 * u), rng.uniform(-.8, .8))
sparkle(10.2); note(10.22, 77, .55, .1, .5)
sparkle(11.8); note(11.82, 81, .55, -.1, .5)

# ---- whoosh under each theme flip ---------------------------------------------
def whoosh(dur, f_a, f_b):
    n = int(SR * dur); x = rng.normal(0, 1, n); y = np.zeros(n); z = 0.0
    fc = f_a * (f_b / f_a) ** (np.arange(n) / n)
    a = 1 - np.exp(-2 * np.pi * fc / SR)
    for i in range(n): z += a[i] * (x[i] - z); y[i] = z
    u = np.arange(n) / n
    return y * np.sin(np.pi * u) ** 1.5
place(wet, whoosh(.9, 220, 1800), ON1 - .05, .05)
place(wet, whoosh(.9, 1600, 200), OFF1 - .05, .045)
place(wet, whoosh(1.1, 220, 2200), ON2 - .05, .06)

# ---- reverb ------------------------------------------------------------------
rn = int(SR * 2.6); rt = np.arange(rn) / SR
ir = rng.normal(0, 1, (rn, 2)) * np.exp(-rt / .55)[:, None]
ir = sosfilt(butter(2, [180, 6500], 'bandpass', fs=SR, output='sos'), ir, axis=0)
ir /= np.sqrt((ir ** 2).sum(0)).mean()
rev = np.stack([fftconvolve(wet[:, c], ir[:, c])[:N] for c in (0, 1)], 1)
mpad = np.stack([fftconvolve(music[:, c], ir[:, c])[:N] for c in (0, 1)], 1)
mix = music * .85 + mpad * .15 + wet + rev * .28

# ---- UI clicks (dry, on top) ---------------------------------------------------
def tick(f, dec, noise=.5):
    n = int(SR * .06); t = np.arange(n) / SR
    body = np.sin(2 * np.pi * (f * t + f * .35 * dec * (1 - np.exp(-t / dec)))) * np.exp(-t / dec)
    hiss = sosfilt(butter(2, 2500, 'highpass', fs=SR, output='sos'), rng.normal(0, 1, n)) * np.exp(-t / .0035)
    return (body + noise * hiss) * np.minimum(1, t / .0005)
def thock():
    n = int(SR * .16); t = np.arange(n) / SR
    f = 95 + 90 * np.exp(-t / .02)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / .05) * np.minimum(1, t / .002)
ui = np.zeros((N, 2)); duck = np.ones(N)
for t, theme in ((1.8, True), (5.4, True), (10.1, False), (11.7, False), (15.7, True)):
    place(ui, tick(1150, .011, .8), t, .40)                   # press
    place(ui, tick(1700, .008, .6), t + .1, .28)              # release
    if theme: place(ui, thock(), t + .1, .32)                 # the knob landing
    duck *= 1 - .45 * np.exp(-np.maximum(0, t_all - t) / .16) * (t_all >= t - .01)
mix = mix * duck[:, None] + ui

# ---- master ------------------------------------------------------------------
mix = sosfilt(butter(2, 55, 'highpass', fs=SR, output='sos'), mix, axis=0)
fade = np.minimum(1, t_all / .03) * np.minimum(1, (DUR - t_all) / .25).clip(0, 1)
mix *= fade[:, None]
gain = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
mix = mix * gain
over = np.abs(mix) > .55                                     # linear below, soft knee above: only click peaks reach it
mix[over] = np.sign(mix[over]) * (.55 + .15 * np.tanh((np.abs(mix[over]) - .55) / .15))
print('peak', round(float(np.abs(mix).max()), 3), 'rms', round(float(np.sqrt((mix ** 2).mean())), 4))
w = wave.open(sys.argv[1], 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((np.clip(mix, -1, 1) * 32767).astype('<i2').tobytes()); w.close()
