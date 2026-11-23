import os
import struct
import zlib
import math

W = H = 1024
OUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", ".")

# ---------- tiny raster canvas ----------
class Canvas:
    def __init__(self, w, h, bg=(10, 12, 20)):
        if w <= 0 or h <= 0:
            raise ValueError("canvas dimensions must be positive")
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        r, g, b = bg
        for i in range(w * h):
            self.px[i*3] = r
            self.px[i*3+1] = g
            self.px[i*3+2] = b

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = c[0]
            self.px[i+1] = c[1]
            self.px[i+2] = c[2]

    def blend(self, x, y, c, a):
        if 0 <= x < self.w and 0 <= y < self.h:
            if a <= 0.0:
                return
            if a >= 1.0:
                self.set(x, y, c)
                return
            i = (y * self.w + x) * 3
            for k in range(3):
                self.px[i+k] = int(self.px[i+k] * (1 - a) + c[k] * a)

    def rect(self, x0, y0, x1, y1, c):
        x0 = max(0, int(x0)); y0 = max(0, int(y0))
        x1 = min(self.w, int(x1)); y1 = min(self.h, int(y1))
        if x0 >= x1 or y0 >= y1:
            return
        cr, cg, cb = c
        for y in range(y0, y1):
            base = y * self.w * 3
            for x in range(x0, x1):
                i = base + x * 3
                self.px[i] = cr; self.px[i+1] = cg; self.px[i+2] = cb

    def rect_a(self, x0, y0, x1, y1, c, a):
        x0 = max(0, int(x0)); y0 = max(0, int(y0))
        x1 = min(self.w, int(x1)); y1 = min(self.h, int(y1))
        if x0 >= x1 or y0 >= y1 or a <= 0.0:
            return
        for y in range(y0, y1):
            for x in range(x0, x1):
                self.blend(x, y, c, a)

    def rrect(self, x0, y0, x1, y1, r, c, a=1.0):
        if x1 <= x0 or y1 <= y0:
            return
        r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
        for y in range(int(y0), int(y1)):
            for x in range(int(x0), int(x1)):
                dx = 0.0; dy = 0.0
                if x < x0 + r: dx = (x0 + r) - x
                elif x > x1 - r: dx = x - (x1 - r)
                if y < y0 + r: dy = (y0 + r) - y
                elif y > y1 - r: dy = y - (y1 - r)
                if dx * dx + dy * dy <= r * r:
                    if a >= 1.0:
                        self.set(x, y, c)
                    else:
                        self.blend(x, y, c, a)

    def line(self, x0, y0, x1, y1, c, w=1):
        dx = x1 - x0; dy = y1 - y0
        steps = int(max(abs(dx), abs(dy))) + 1
        half = max(0, w // 2)
        for s in range(steps + 1):
            t = s / steps
            x = int(x0 + dx * t); y = int(y0 + dy * t)
            for oy in range(-half, half + 1):
                for ox in range(-half, half + 1):
                    self.set(x + ox, y + oy, c)

    def disc(self, cx, cy, r, c, a=1.0):
        if r <= 0:
            return
        r2 = r * r
        for y in range(int(cy - r), int(cy + r) + 1):
            for x in range(int(cx - r), int(cx + r) + 1):
                d = (x - cx) ** 2 + (y - cy) ** 2
                if d <= r2:
                    if a >= 1.0:
                        self.set(x, y, c)
                    else:
                        self.blend(x, y, c, a)

    def ring(self, cx, cy, r, thick, c, a=1.0):
        if r <= 0 or thick <= 0:
            return
        ro = r + thick / 2; ri = max(0.0, r - thick / 2)
        for y in range(int(cy - ro), int(cy + ro) + 1):
            for x in range(int(cx - ro), int(cx + ro) + 1):
                d = math.hypot(x - cx, y - cy)
                if ri <= d <= ro:
                    if a >= 1.0:
                        self.set(x, y, c)
                    else:
                        self.blend(x, y, c, a)

    def png(self):
        raw = bytearray()
        stride = self.w * 3
        for y in range(self.h):
            raw.append(0)
            raw += self.px[y*stride:(y+1)*stride]
        comp = zlib.compress(bytes(raw), 9)

        def chunk(tag, data):
            return (struct.pack(">I", len(data)) + tag + data +
                    struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))

        sig = b"\x89PNG\r\n\x1a\n"
        ihdr = struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0)
        return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", comp) + chunk(b"IEND", b"")

# ---------- 5x7 bitmap font ----------
FONT = {
 'A':["01110","10001","10001","11111","10001","10001","10001"],
 'B':["11110","10001","10001","11110","10001","10001","11110"],
 'C':["01110","10001","10000","10000","10000","10001","01110"],
 'D':["11110","10001","10001","10001","10001","10001","11110"],
 'E':["11111","10000","10000","11110","10000","10000","11111"],
 'F':["11111","10000","10000","11110","10000","10000","10000"],
 'G':["01110","10001","10000","10111","10001","10001","01111"],
 'H':["10001","10001","10001","11111","10001","10001","10001"],
 'I':["11111","00100","00100","00100","00100","00100","11111"],
 'J':["00111","00010","00010","00010","00010","10010","01100"],
 'K':["10001","10010","10100","11000","10100","10010","10001"],
 'L':["10000","10000","10000","10000","10000","10000","11111"],
 'M':["10001","11011","10101","10101","10001","10001","10001"],
 'N':["10001","11001","10101","10011","10001","10001","10001"],
 'O':["01110","10001","10001","10001","10001","10001","01110"],
 'P':["11110","10001","10001","11110","10000","10000","10000"],
 'Q':["01110","10001","10001","10001","10101","10010","01101"],
 'R':["11110","10001","10001","11110","10100","10010","10001"],
 'S':["01111","10000","10000","01110","00001","00001","11110"],
 'T':["11111","00100","00100","00100","00100","00100","00100"],
 'U':["10001","10001","10001","10001","10001","10001","01110"],
 'V':["10001","10001","10001","10001","10001","01010","00100"],
 'W':["10001","10001","10001","10101","10101","10101","01010"],
 'X':["10001","10001","01010","00100","01010","10001","10001"],
 'Y':["10001","10001","01010","00100","00100","00100","00100"],
 'Z':["11111","00001","00010","00100","01000","10000","11111"],
 '0':["01110","10001","10011","10101","11001","10001","01110"],
 '1':["00100","01100","00100","00100","00100","00100","01110"],
 '2':["01110","10001","00001","00010","00100","01000","11111"],
 '3':["11111","00010","00100","00010","00001","10001","01110"],
 '4':["00010","00110","01010","10010","11111","00010","00010"],
 '5':["11111","10000","11110","00001","00001","10001","01110"],
 '6':["00110","01000","10000","11110","10001","10001","01110"],
 '7':["11111","00001","00010","00100","01000","01000","01000"],
 '8':["01110","10001","10001","01110","10001","10001","01110"],
 '9':["01110","10001","10001","01111","00001","00010","01100"],
 ' ':["00000"]*7,
 '.':["00000","00000","00000","00000","00000","01100","01100"],
 ',':["00000","00000","00000","00000","01100","01100","00100"],
 '-':["00000","00000","00000","11111","00000","00000","00000"],
 '&':["01100","10010","10100","01000","10101","10010","01101"],
 '/':["00001","00010","00010","00100","01000","01000","10000"],
 ':':["00000","01100","01100","00000","01100","01100","00000"],
 '!':["00100","00100","00100","00100","00100","00000","00100"],
 "'":["00100","00100","00000","00000","00000","00000","00000"],
}
GLYPH_W = 5
GLYPH_H = 7
ADVANCE = GLYPH_W + 1

def text(cv, x, y, s, scale, c, a=1.0):
    if scale <= 0:
        return x
    cx = x
    for ch in s.upper():
        g = FONT.get(ch, FONT[' '])
        for ry in range(GLYPH_H):
            row = g[ry] if ry < len(g) else "00000"
            for rx in range(GLYPH_W):
                if rx < len(row) and row[rx] == '1':
                    for sy in range(scale):
                        for sx in range(scale):
                            if a >= 1.0:
                                cv.set(cx + rx*scale + sx, y + ry*scale + sy, c)
                            else:
                                cv.blend(cx + rx*scale + sx, y + ry*scale + sy, c, a)
        cx += ADVANCE * scale
    return cx

def text_w(s, scale):
    if not s or scale <= 0:
        return 0
    return len(s) * ADVANCE * scale - scale

def text_center(cv, y, s, scale, c, a=1.0):
    x = (W - text_w(s, scale)) // 2
    text(cv, x, y, s, scale, c, a)

# ---------- palette ----------
BG_TOP = (8, 10, 22)
BG_BOT = (22, 14, 34)
WHITE = (240, 244, 252)
DIM = (150, 160, 185)
ACCENT = (255, 90, 90)
GOLD = (255, 200, 70)
CYAN = (90, 210, 240)
GREEN = (110, 220, 150)

def main():
    cv = Canvas(W, H)

    # vertical gradient background
    for y in range(H):
        t = y / (H - 1)
        r = int(BG_TOP[0] * (1 - t) + BG_BOT[0] * t)
        g = int(BG_TOP[1] * (1 - t) + BG_BOT[1] * t)
        b = int(BG_TOP[2] * (1 - t) + BG_BOT[2] * t)
        cv.rect(0, y, W, y + 1, (r, g, b))

    # subtle globe grid backdrop (world news motif)
    gcx, gcy, gr = 512, 560, 380
    for lat in range(-60, 61, 20):
        ry = gr * math.sin(math.radians(lat))
        rx = gr * math.cos(math.radians(lat))
        if rx <= 0:
            continue
        y = int(gcy + ry)
        for x in range(int(gcx - rx), int(gcx + rx) + 1):
            cv.blend(x, y, (50, 58, 88), 0.30)
    for lon in range(0, 180, 20):
        ph = math.radians(lon)
        for y in range(int(gcy - gr), int(gcy + gr) + 1):
            dy = (y - gcy) / gr
            if -1 <= dy <= 1:
                x = gcx + gr * math.cos(math.asin(dy)) * math.cos(ph)
                cv.blend(int(x), y, (50, 58, 88), 0.30)
                cv.blend(int(gcx - (x - gcx)), y, (50, 58, 88), 0.30)

    # header band
    cv.rect_a(0, 0, W, 150, (5, 6, 14), 0.55)
    cv.rect(0, 148, W, 152, ACCENT)
    text_center(cv, 30, "WORLD NEWS", 4, WHITE)
    text_center(cv, 72, "MONDAY 23 NOVEMBER 2026", 3, GOLD)
    text_center(cv, 112, "THE DAY IN ONE PICTURE", 2, DIM)

    # ---- central headline card ----
    card_x0, card_y0, card_x1, card_y1 = 92, 200, 932, 470
    cv.rrect(card_x0, card_y0, card_x1, card_y1, 26, (16, 20, 38), 0.92)
    border = (70, 82, 120)
    for x in range(card_x0 + 26, card_x1 - 26):
        cv.set(x, card_y0, border)
        cv.set(x, card_y1 - 1, border)
    for y in range(card_y0 + 26, card_y1 - 26):
        cv.set(card_x0, y, border)
        cv.set(card_x1 - 1, y, border)

    text_center(cv, 232, "A WORLD IN MOTION", 4, WHITE)
    text_center(cv, 290, "CONFLICT  CLIMATE  ECONOMY", 2, CYAN)
    text_center(cv, 330, "AI  DIPLOMACY  SPORT", 2, CYAN)
    text_center(cv, 388, "ONE DAY, MANY STORIES", 3, GOLD)

    # ---- three story tiles ----
    tiles = [
        ("PEACE TALKS", "DIPLOMACY", GREEN),
        ("CLIMATE SUMMIT", "THE PLANET", CYAN),
        ("MARKETS RALLY", "ECONOMY", GOLD),
    ]
    ty0, ty1 = 510, 700
    tw = 270
    gap = 30
    tx0 = (W - (tw * 3 + gap * 2)) // 2
    for i, (title, sub, col) in enumerate(tiles):
        x0 = tx0 + i * (tw + gap)
        x1 = x0 + tw
        cv.rrect(x0, ty0, x1, ty1, 18, (18, 22, 42), 0.95)
        cv.rrect(x0 + 14, ty0 + 14, x1 - 14, ty0 + 22, 4, col, 1.0)
        icx = (x0 + x1) // 2
        icy = ty0 + 78
        if i == 0:
            cv.disc(icx - 22, icy, 16, col, 0.9)
            cv.disc(icx + 22, icy, 16, col, 0.9)
            cv.rect(icx - 22, icy - 6, icx + 22, icy + 6, col)
        elif i == 1:
            cv.disc(icx, icy, 26, col, 0.85)
            cv.ring(icx, icy, 26, 3, WHITE, 0.8)
            cv.line(icx - 26, icy, icx + 26, icy, (10, 12, 20), 2)
            cv.line(icx, icy - 26, icx, icy + 26, (10, 12, 20), 2)
        else:
            for k, bh in enumerate((18, 32, 48)):
                bx = icx - 30 + k * 22
                cv.rect(bx, icy + 26 - bh, bx + 14, icy + 26, col)
            cv.line(icx - 30, icy + 10, icx + 30, icy - 20, WHITE, 2)
        text_center(cv, ty0 + 130, title, 2, WHITE)
        text_center(cv, ty0 + 160, sub, 1, DIM)

    # ---- ticker strip ----
    tick_y0, tick_y1 = 740, 800
    cv.rect_a(0, tick_y0, W, tick_y1, (5, 6, 14), 0.7)
    cv.rect(0, tick_y0, W, tick_y0 + 2, GOLD)
    cv.rect(0, tick_y1 - 2, W, tick_y1, GOLD)
    text(cv, 40, tick_y0 + 22, "LIVE  |  LEADERS MEET  |  CLIMATE DEAL  |  STOCKS UP  |  AI ACCORD", 2, WHITE)

    # ---- footer ----
    text_center(cv, 840, "23 NOVEMBER 2026", 3, WHITE)
    text_center(cv, 890, "A SINGLE FRAME OF A MOVING WORLD", 2, DIM)
    text_center(cv, 940, "NEWS IMAGE  -  MAKE.FUN", 2, ACCENT)

    # corner marks
    for (cx, cy, sx, sy) in [(30, 30, 1, 1), (W-30, 30, -1, 1), (30, H-30, 1, -1), (W-30, H-30, -1, -1)]:
        cv.line(cx, cy, cx + 40*sx, cy, ACCENT, 2)
        cv.line(cx, cy, cx, cy + 40*sy, ACCENT, 2)

    data = cv.png()
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "entry.png")
    with open(out_path, "wb") as f:
        f.write(data)
    print("wrote entry.png", len(data), "bytes")

if __name__ == "__main__":
    main()