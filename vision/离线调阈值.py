# UI: Main button -> Threshold Editor (MaixCAM / MaixPy v4)
# 修复点：相机不要用 FMT_RGB565（很多固件/驱动不支持），改用 RGB888 或默认格式。
#
# 主界面：实时相机画面 + 中央淡蓝色块 “Threshold Editor”（黑字）
# 点击色块：进入阈值编辑界面（实时画面背景 + 简易 LAB 阈值面板 + Back）
#
# 触摸坐标：触摸返回的是“屏幕坐标”，显示相机画面常用 FIT_CONTAIN，会缩放并留边，
#           因此需要用 image.resize_map_pos_reverse() 将屏幕坐标映射回图像坐标，
#           才不会“点偏”。

from maix import camera, display, image, app, touchscreen

# -----------------------------
# Helpers
# -----------------------------
def in_rect(px, py, rect):
    x, y, w, h = rect
    return (px >= x) and (px < x + w) and (py >= y) and (py < y + h)

def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

def map_touch_to_img(x_disp, y_disp, img_w, img_h, disp_w, disp_h, fit):
    # screen -> image coord mapping
    x_img, y_img = image.resize_map_pos_reverse(img_w, img_h, disp_w, disp_h, fit, x_disp, y_disp)
    return int(x_img), int(y_img)

# -----------------------------
# Threshold editor
# -----------------------------
class ThresholdEditor:
    """
    点击式阈值编辑：
      - 点某一行选择参数（Lmin/Lmax/Amin/Amax/Bmin/Bmax）
      - 点 '-' / '+' 调数值
      - 点 STEP 切换步长 1/5/10
      - 点 SAVE 打印阈值到串口/控制台
    """
    def __init__(self, init_th=None):
        self.th = init_th[:] if init_th else [0, 100, 25, 90, 0, 90]
        self.names = ["Lmin", "Lmax", "Amin", "Amax", "Bmin", "Bmax"]
        self.sel = 2
        self.steps = [1, 5, 10]
        self.step_i = 0

        # Panel layout (in IMAGE coordinates)
        self.panel_w = 160
        self.row_h = 22
        self.pad = 4

        self.btn_minus = None
        self.btn_plus = None
        self.btn_step = None
        self.btn_save = None

    def on_click(self, x, y):
        # 参数列表区域
        list_x = self.pad
        list_y = self.pad
        list_w = self.panel_w - 2 * self.pad
        list_h = 6 * self.row_h

        if in_rect(x, y, (list_x, list_y, list_w, list_h)):
            idx = (y - list_y) // self.row_h
            if 0 <= idx < 6:
                self.sel = int(idx)
            return

        # 按钮
        if self.btn_minus and in_rect(x, y, self.btn_minus):
            self._adjust(-self.steps[self.step_i]); return
        if self.btn_plus and in_rect(x, y, self.btn_plus):
            self._adjust(+self.steps[self.step_i]); return
        if self.btn_step and in_rect(x, y, self.btn_step):
            self.step_i = (self.step_i + 1) % len(self.steps); return
        if self.btn_save and in_rect(x, y, self.btn_save):
            print("LAB threshold =", self.th); return

    def _adjust(self, delta):
        i = self.sel
        self.th[i] += int(delta)

        # 常见 LAB 范围
        if i in (0, 1):   # L
            self.th[i] = clamp(self.th[i], 0, 100)
        else:            # A/B
            self.th[i] = clamp(self.th[i], -128, 127)

        # 保证 min <= max
        if self.th[0] > self.th[1]: self.th[0], self.th[1] = self.th[1], self.th[0]
        if self.th[2] > self.th[3]: self.th[2], self.th[3] = self.th[3], self.th[2]
        if self.th[4] > self.th[5]: self.th[4], self.th[5] = self.th[5], self.th[4]

    def draw(self, img):
        # 面板背景
        img.draw_rect(0, 0, self.panel_w, img.height(), image.COLOR_BLACK, thickness=-1)
        img.draw_rect(0, 0, self.panel_w, img.height(), image.COLOR_WHITE, thickness=1)

        # 参数行
        x0 = self.pad
        y0 = self.pad
        for i in range(6):
            y = y0 + i * self.row_h
            if i == self.sel:
                img.draw_rect(1, y, self.panel_w - 2, self.row_h, image.COLOR_BLUE, thickness=-1)
            img.draw_string(x0 + 2, y + 4, f"{self.names[i]}: {self.th[i]}", image.COLOR_WHITE)

        # 按钮
        btn_y = y0 + 6 * self.row_h + self.pad
        bw = (self.panel_w - 3 * self.pad) // 2
        bh = 26

        self.btn_minus = (self.pad, btn_y, bw, bh)
        self.btn_plus  = (2 * self.pad + bw, btn_y, bw, bh)
        img.draw_rect(*self.btn_minus, image.COLOR_WHITE, thickness=1)
        img.draw_rect(*self.btn_plus,  image.COLOR_WHITE, thickness=1)
        img.draw_string(self.btn_minus[0] + 10, self.btn_minus[1] + 6, "-", image.COLOR_WHITE)
        img.draw_string(self.btn_plus[0] + 10,  self.btn_plus[1] + 6, "+", image.COLOR_WHITE)

        btn_y2 = btn_y + bh + self.pad
        self.btn_step = (self.pad, btn_y2, bw, bh)
        self.btn_save = (2 * self.pad + bw, btn_y2, bw, bh)
        img.draw_rect(*self.btn_step, image.COLOR_WHITE, thickness=1)
        img.draw_rect(*self.btn_save, image.COLOR_WHITE, thickness=1)
        img.draw_string(self.btn_step[0] + 6, self.btn_step[1] + 6, f"STEP:{self.steps[self.step_i]}", image.COLOR_WHITE)
        img.draw_string(self.btn_save[0] + 6, self.btn_save[1] + 6, "SAVE", image.COLOR_WHITE)

# -----------------------------
# Main
# -----------------------------
W, H = 320, 240
FIT_MODE = image.Fit.FIT_CONTAIN

disp = display.Display()
ts = touchscreen.TouchScreen()

# ✅ 相机格式：先尝试 RGB888；若固件不支持/枚举不兼容，则退回默认 Camera(W,H)
try:
    cam = camera.Camera(W, H, image.Format.FMT_RGB888, buff_num=1)
except Exception as e:
    print("RGB888 not available, fallback to default Camera(W,H). err =", e)
    cam = camera.Camera(W, H)  # 默认 RGB 输出（文档就是这样用的）:contentReference[oaicite:2]{index=2}

LIGHT_BLUE = image.Color.from_rgb(173, 216, 230)  # 淡蓝色
BLACK = image.COLOR_BLACK
WHITE = image.COLOR_WHITE

STATE_MAIN = 0
STATE_EDITOR = 1
state = STATE_MAIN

editor = ThresholdEditor(init_th=[0, 100, 25, 90, 0, 90])

# click edge detection：按下->松开 视为一次 click
pressed_down = False
click_disp = None

# 可选：编辑页叠加 blob 预览
PIXELS_TH = 20
AREA_TH = 20

while not app.need_exit():
    img = cam.read()

    # ---- touch (non-blocking if available exists)
    click_disp = None
    if hasattr(ts, "available"):
        if ts.available(0):
            x_disp, y_disp, pressed = ts.read()
            if pressed:
                pressed_down = True
            else:
                if pressed_down:
                    pressed_down = False
                    click_disp = (x_disp, y_disp)
    else:
        # fallback: direct read
        x_disp, y_disp, pressed = ts.read()
        if pressed:
            pressed_down = True
        else:
            if pressed_down:
                pressed_down = False
                click_disp = (x_disp, y_disp)

    # 屏幕坐标 -> 图像坐标（保证按钮命中准确）
    click_img = None
    if click_disp is not None:
        cx, cy = map_touch_to_img(click_disp[0], click_disp[1],
                                  img.width(), img.height(),
                                  disp.width(), disp.height(),
                                  FIT_MODE)
        click_img = (cx, cy)

    # ---- UI state machine
    if state == STATE_MAIN:
        # 中央按钮（淡蓝底 + 黑字）
        btn_w = int(img.width() * 0.70)
        btn_h = int(img.height() * 0.20)
        btn_x = (img.width() - btn_w) // 2
        btn_y = (img.height() - btn_h) // 2
        btn_rect = (btn_x, btn_y, btn_w, btn_h)

        # 点击进入编辑页
        if click_img is not None and in_rect(click_img[0], click_img[1], btn_rect):
            state = STATE_EDITOR

        # 画按钮
        img.draw_rect(btn_x, btn_y, btn_w, btn_h, LIGHT_BLUE, thickness=-1)  # 填充淡蓝
        img.draw_rect(btn_x, btn_y, btn_w, btn_h, BLACK, thickness=2)        # 黑边框
        img.draw_string(btn_x + 12, btn_y + (btn_h // 2) - 8, "Threshold Editor", BLACK)

    else:
        # 编辑页：右上 Back
        back_w, back_h = 70, 28
        back_x = img.width() - back_w - 6
        back_y = 6
        back_rect = (back_x, back_y, back_w, back_h)

        if click_img is not None and in_rect(click_img[0], click_img[1], back_rect):
            state = STATE_MAIN
        else:
            if click_img is not None:
                editor.on_click(click_img[0], click_img[1])

        # 可选：把当前阈值的 blob 画出来，方便你一边调一边看效果
        blobs = img.find_blobs([editor.th], pixels_threshold=PIXELS_TH, area_threshold=AREA_TH)
        for b in blobs:
            x, y, w, h = int(b[0]), int(b[1]), int(b[2]), int(b[3])
            img.draw_rect(x, y, w, h, image.COLOR_RED, thickness=2)

        editor.draw(img)

        # Back按钮
        img.draw_rect(back_x, back_y, back_w, back_h, WHITE, thickness=1)
        img.draw_string(back_x + 10, back_y + 6, "Back", WHITE)
        img.draw_string(170, 40, f"TH:{editor.th}", image.COLOR_YELLOW)

    disp.show(img, fit=FIT_MODE)