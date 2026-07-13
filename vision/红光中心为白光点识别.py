# MaixCAM 激光点检测（抗瓷砖反光版本）

from maix import camera, display, image, app
import time

APP_ITEM = "app_find_blobs"
LAB_KEYS = ("user_lmin", "user_lmax", "user_amin", "user_amax", "user_bmin", "user_bmax")

DEFAULT_RED_THRESHOLDS = [[0, 80, 40, 80, 10, 80]]

PIXELS_THRESHOLD = 10
AREA_THRESHOLD = 10

TRACK_ROI_HALF = 40

# 激光点面积限制
MAX_LASER_AREA = 1000

# 白色中心判断阈值
WHITE_L_THRESHOLD = 60


def load_thresholds_from_editor():
    vals = []
    try:
        for k in LAB_KEYS:
            s = app.get_app_config_kv(APP_ITEM, k, "", False)
            if not s:
                return []
            vals.append(int(s))
        return [vals]
    except Exception:
        return []


def clamp_roi(x, y, w, h, img_w, img_h):
    x = max(0, min(x, img_w - 1))
    y = max(0, min(y, img_h - 1))
    w = max(1, min(w, img_w - x))
    h = max(1, min(h, img_h - y))
    return [x, y, w, h]


# 判断blob中心是否为高亮白色
def has_white_center(img, blob):
    x, y, w, h = blob[0], blob[1], blob[2], blob[3]

    cx = x + w // 2
    cy = y + h // 2

    roi_size = max(2, min(w, h) // 3)

    roi = [
        cx - roi_size // 2,
        cy - roi_size // 2,
        roi_size,
        roi_size
    ]

    stats = img.get_statistics(roi=roi)

    return stats.l_mean() > WHITE_L_THRESHOLD


# 选择最佳激光点
def pick_best_blob(img, blobs, last_xy=None):

    candidates = []

    for b in blobs:

        x, y, w, h = b[0], b[1], b[2], b[3]

        # 面积过滤
        if w * h > MAX_LASER_AREA:
            continue

        # 必须有白色核心
        if not has_white_center(img, b):
            continue

        candidates.append(b)

    if not candidates:
        return None

    # 如果有历史位置 → 选最近
    if last_xy is not None:

        lx, ly = last_xy
        best = None
        best_d2 = None

        for b in candidates:

            x, y, w, h = b[0], b[1], b[2], b[3]
            cx = x + w // 2
            cy = y + h // 2

            d2 = (cx - lx) ** 2 + (cy - ly) ** 2

            if best is None or d2 < best_d2:
                best = b
                best_d2 = d2

        return best

    # 没有历史 → 选最大
    return max(candidates, key=lambda b: b[2] * b[3])


def main():

    thresholds = load_thresholds_from_editor()

    if not thresholds:
        thresholds = DEFAULT_RED_THRESHOLDS
        print("[WARN] 使用默认红色阈值:", thresholds)
    else:
        print("[OK] 已读取阈值:", thresholds)

    cam = camera.Camera(640, 480, fps=60)
    disp = display.Display()

    last_xy = None
    last_seen_t = 0

    while True:

        img = cam.read()
        if img is None:
            continue

        roi = None
        now = time.time()

        # ROI追踪
        if last_xy is not None and (now - last_seen_t) < 0.5:

            cx, cy = last_xy

            roi = clamp_roi(
                cx - TRACK_ROI_HALF,
                cy - TRACK_ROI_HALF,
                TRACK_ROI_HALF * 2,
                TRACK_ROI_HALF * 2,
                img.width(),
                img.height()
            )

        if roi:

            blobs = img.find_blobs(
                thresholds,
                roi=roi,
                pixels_threshold=PIXELS_THRESHOLD,
                area_threshold=AREA_THRESHOLD
            )

            img.draw_rect(roi[0], roi[1], roi[2], roi[3], image.COLOR_BLUE)

        else:

            blobs = img.find_blobs(
                thresholds,
                pixels_threshold=PIXELS_THRESHOLD,
                area_threshold=AREA_THRESHOLD
            )

        best = pick_best_blob(img, blobs, last_xy)

        if best:

            x, y, w, h = best[0], best[1], best[2], best[3]

            cx = x + w // 2
            cy = y + h // 2

            img.draw_rect(x, y, w, h, image.COLOR_GREEN)

            img.draw_line(cx - 8, cy, cx + 8, cy, image.COLOR_RED, 2)
            img.draw_line(cx, cy - 8, cx, cy + 8, image.COLOR_RED, 2)

            img.draw_string(0, 0, f"Laser ({cx},{cy})", image.COLOR_YELLOW)

            print(cx, cy)

            last_xy = (cx, cy)
            last_seen_t = now

        else:

            if last_xy and (now - last_seen_t) > 1:
                last_xy = None

        disp.show(img)


if __name__ == "__main__":
    main()