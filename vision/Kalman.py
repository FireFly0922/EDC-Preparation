from maix import camera, display, image, app, time


# =========================
# 1. 简单 2D 匀速模型卡尔曼滤波器
# 状态量: [x, y, vx, vy]
# 观测量: [x, y]
# =========================
class Kalman2D:
    def __init__(self, x=0.0, y=0.0):
        self.x = [[x], [y], [0.0], [0.0]]

        # 状态协方差 P，初始给大一点，表示刚开始不太相信预测
        self.P = [
            [100.0, 0.0,   0.0,   0.0],
            [0.0,   100.0, 0.0,   0.0],
            [0.0,   0.0,   100.0, 0.0],
            [0.0,   0.0,   0.0,   100.0],
        ]

        # 过程噪声：越大，越相信目标可能突然加速/抖动
        self.q_pos = 0.05
        self.q_vel = 1.0

        # 观测噪声：越大，越不相信检测到的红点位置
        self.r = 25.0

        self.inited = False

    def _matmul(self, A, B):
        rows = len(A)
        cols = len(B[0])
        inner = len(B)
        C = [[0.0 for _ in range(cols)] for _ in range(rows)]
        for i in range(rows):
            for j in range(cols):
                s = 0.0
                for k in range(inner):
                    s += A[i][k] * B[k][j]
                C[i][j] = s
        return C

    def _transpose(self, A):
        return [list(row) for row in zip(*A)]

    def _add(self, A, B):
        return [[A[i][j] + B[i][j] for j in range(len(A[0]))] for i in range(len(A))]

    def _sub(self, A, B):
        return [[A[i][j] - B[i][j] for j in range(len(A[0]))] for i in range(len(A))]

    def _inv2(self, S):
        a, b = S[0][0], S[0][1]
        c, d = S[1][0], S[1][1]
        det = a * d - b * c
        if abs(det) < 1e-9:
            det = 1e-9
        return [
            [d / det, -b / det],
            [-c / det, a / det],
        ]

    def reset(self, x, y):
        self.x = [[float(x)], [float(y)], [0.0], [0.0]]
        self.P = [
            [100.0, 0.0,   0.0,   0.0],
            [0.0,   100.0, 0.0,   0.0],
            [0.0,   0.0,   100.0, 0.0],
            [0.0,   0.0,   0.0,   100.0],
        ]
        self.inited = True

    def predict(self, dt):
        if not self.inited:
            return None

        F = [
            [1.0, 0.0, dt,  0.0],
            [0.0, 1.0, 0.0, dt],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]

        Q = [
            [self.q_pos, 0.0,        0.0,        0.0],
            [0.0,        self.q_pos, 0.0,        0.0],
            [0.0,        0.0,        self.q_vel, 0.0],
            [0.0,        0.0,        0.0,        self.q_vel],
        ]

        self.x = self._matmul(F, self.x)
        Ft = self._transpose(F)
        self.P = self._add(self._matmul(self._matmul(F, self.P), Ft), Q)

        return self.get_pos()

    def update(self, mx, my):
        if not self.inited:
            self.reset(mx, my)
            return self.get_pos()

        H = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
        ]

        R = [
            [self.r, 0.0],
            [0.0, self.r],
        ]

        z = [[float(mx)], [float(my)]]

        # y = z - Hx
        y = self._sub(z, self._matmul(H, self.x))

        # S = HPH^T + R
        Ht = self._transpose(H)
        S = self._add(self._matmul(self._matmul(H, self.P), Ht), R)
        S_inv = self._inv2(S)

        # K = PH^T S^-1
        K = self._matmul(self._matmul(self.P, Ht), S_inv)

        # x = x + Ky
        self.x = self._add(self.x, self._matmul(K, y))

        # P = (I - KH)P
        I = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        KH = self._matmul(K, H)
        self.P = self._matmul(self._sub(I, KH), self.P)

        return self.get_pos()

    def get_pos(self):
        return int(self.x[0][0]), int(self.x[1][0])


# =========================
# 2. 红色光点检测
# =========================
def find_red_light(img):
    # 官方文档中的红色 LAB 阈值示例为 [0, 80, 40, 80, 10, 80]
    # 红色激光/LED 在不同曝光下差异很大，下面先给一个较宽的红色阈值。
    # 若误检多，请用 MaixCAM 自带“找色块”应用重新调 LAB 阈值。
    red_thresholds = [
        [0, 100, 35, 127, -20, 127],
    ]

    blobs = img.find_blobs(
        red_thresholds,
        pixels_threshold=5,
        area_threshold=5
    )

    if not blobs:
        return None

    # 选择面积最大的红色色块，避免把噪点当成目标
    best = None
    best_area = 0

    for b in blobs:
        x = int(b[0])
        y = int(b[1])
        w = int(b[2])
        h = int(b[3])
        area = w * h

        # 过滤过大的红色区域，避免红色背景/红色物体干扰
        if area < 5:
            continue
        if area > 3000:
            continue

        if area > best_area:
            best_area = area
            best = (x, y, w, h)

    if best is None:
        return None

    x, y, w, h = best
    cx = x + w // 2
    cy = y + h // 2
    return x, y, w, h, cx, cy


# =========================
# 3. 主程序
# =========================
cam = camera.Camera(320, 240)
disp = display.Display()

kf = Kalman2D()

last_ms = time.ticks_ms()
lost_count = 0
MAX_LOST = 15

while not app.need_exit():
    now_ms = time.ticks_ms()
    dt = (now_ms - last_ms) / 1000.0
    last_ms = now_ms

    # 防止 dt 异常过大或过小
    if dt <= 0.0:
        dt = 1.0 / 30.0
    if dt > 0.2:
        dt = 0.2

    img = cam.read()

    # 先预测
    pred = kf.predict(dt)

    # 再检测红色光点
    det = find_red_light(img)

    if det is not None:
        x, y, w, h, mx, my = det

        # 有观测值，用观测值修正卡尔曼滤波器
        fx, fy = kf.update(mx, my)
        lost_count = 0

        # 绿色框：实际检测到的红色色块
        img.draw_rect(x, y, w, h, image.COLOR_GREEN)

        # 红色小框：观测中心
        img.draw_rect(mx - 3, my - 3, 6, 6, image.COLOR_RED)

        # 字符显示
        img.draw_string(5, 5, "TRACKING", color=image.COLOR_GREEN)
        img.draw_string(5, 25, "meas: %d,%d" % (mx, my), color=image.COLOR_GREEN)
        img.draw_string(5, 45, "kalman: %d,%d" % (fx, fy), color=image.COLOR_GREEN)

    else:
        # 没检测到红点，只使用预测值短时间维持轨迹
        lost_count += 1

        if pred is not None and lost_count <= MAX_LOST:
            fx, fy = pred
            img.draw_string(5, 5, "PREDICT", color=image.COLOR_RED)
            img.draw_string(5, 25, "kalman: %d,%d" % (fx, fy), color=image.COLOR_RED)
        else:
            img.draw_string(5, 5, "LOST", color=image.COLOR_RED)

    # 蓝色小框：卡尔曼滤波后的中心位置
    if kf.inited:
        fx, fy = kf.get_pos()
        img.draw_rect(fx - 5, fy - 5, 10, 10, image.COLOR_BLUE)

    disp.show(img)