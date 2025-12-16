import os
import sys
import random
import pygame as pg

WIDTH = 1100
HEIGHT = 650
FPS = 60

# デバッグ：地面ラインを表示するなら True
DEBUG_DRAW_GROUND_LINE = True

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ステージ2へ移行するフレーム（仕様に明記が無いので仮定：25秒相当）
STAGE2_TMR = 1500  # 60FPS想定

# グローバル（現在ステージの接地Y）
GROUND_Y = HEIGHT - 60

# ===== HP/ダメージ（追加）=====
HP_MAX = 100
DMG = 20
POPUP_FRAMES = 120   # 約2秒（60FPS想定）
INV_FRAMES = 30      # 無敵0.5秒（接触中に毎フレーム減るのを防ぐための実装上の仮定）

# ===== 右下UI（Attack/Status）（追加）=====
BOX_W, BOX_H = 220, 110
BOX_GAP = 14
BOX_MARGIN = 20


# =========================
# クラス外関数（メモ準拠）
# =========================
def load_image(filename: str) -> pg.Surface:
    """
    画像読み込み（fig/filename -> filename の順に探す）
    """
    candidates = [os.path.join("fig", filename), filename]
    last_err = None
    for path in candidates:
        try:
            return pg.image.load(path).convert_alpha()
        except Exception as e:
            last_err = e
    raise SystemExit(f"画像 '{filename}' の読み込みに失敗しました: {last_err}")


def check_bound(obj_rct: pg.Rect) -> tuple[bool, bool]:
    yoko, tate = True, True
    if obj_rct.left < 0 or WIDTH < obj_rct.right:
        yoko = False
    if obj_rct.top < 0 or HEIGHT < obj_rct.bottom:
        tate = False
    return yoko, tate


def clamp_in_screen(rect: pg.Rect) -> pg.Rect:
    rect.left = max(0, rect.left)
    rect.right = min(WIDTH, rect.right)
    rect.top = max(0, rect.top)
    rect.bottom = min(HEIGHT, rect.bottom)
    return rect


def get_ground_y() -> int:
    """
    現在ステージの地面Y
    """
    return GROUND_Y


def set_ground_y(v: int) -> None:
    global GROUND_Y
    GROUND_Y = v


def stage_params(stage: int) -> dict:
    """
    ステージごとの設定
    ※追加機能（遷移画面等）は入れない
    """
    if stage == 1:
        return {
            "bg_file": "bg_1.jpg",
            "bg_speed": 4,
            "enemy_speed": 7,
            "spawn_interval": 60,  # フレーム間隔
        }
    return {
        "bg_file": "bg_2.jpg",
        "bg_speed": 6,
        "enemy_speed": 9,
        "spawn_interval": 45,
    }


def should_switch_stage(tmr: int) -> bool:
    """
    ステージ2へ移行する条件（仕様が無いので仮定：一定時間）
    """
    return tmr >= STAGE2_TMR


def spawn_enemy(enemies: pg.sprite.Group, stage: int) -> None:
    enemies.add(Enemy(stage))


def detect_ground_y(bg_scaled: pg.Surface) -> int:
    """
    リサイズ済み背景から「暗くて横方向に均一な水平ライン」を推定し、
    その“1px下”を地面Yとして返す。
    """
    w, h = bg_scaled.get_size()

    y_start = int(h * 0.40)
    y_end = int(h * 0.90)

    x_step = 4
    best_y = int(h * 0.75)
    best_score = 10**18

    for y in range(y_start, y_end):
        s = 0.0
        s2 = 0.0
        n = 0
        for x in range(0, w, x_step):
            r, g, b, a = bg_scaled.get_at((x, y))
            lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
            s += lum
            s2 += lum * lum
            n += 1

        mean = s / n
        var = (s2 / n) - mean * mean
        std = (var ** 0.5) if var > 0 else 0.0

        score = mean + 0.3 * std
        if score < best_score:
            best_score = score
            best_y = y

    return min(h - 1, best_y + 1)


# =========================
# クラス
# =========================
class Background:
    """
    背景を右→左へ強制スクロール（2枚並べてループ）
    """
    def __init__(self, bg_file: str, speed: int):
        raw = load_image(bg_file)
        self._img = pg.transform.smoothscale(raw, (WIDTH, HEIGHT))
        self._speed = speed
        self._x1 = 0
        self._x2 = WIDTH
        set_ground_y(detect_ground_y(self._img))

    def update(self, screen: pg.Surface):
        self._x1 -= self._speed
        self._x2 -= self._speed

        if self._x1 <= -WIDTH:
            self._x1 = self._x2 + WIDTH
        if self._x2 <= -WIDTH:
            self._x2 = self._x1 + WIDTH

        screen.blit(self._img, (self._x1, 0))
        screen.blit(self._img, (self._x2, 0))


class Bird(pg.sprite.Sprite):
    """
    プレイヤー：左右移動＋ジャンプ＋二段ジャンプ
    """
    def __init__(self, num: int, xy: tuple[int, int]):
        super().__init__()
        img0 = pg.transform.rotozoom(load_image(f"{num}.png"), 0, 0.9)
        img = pg.transform.flip(img0, True, False)

        self._imgs = {+1: img, -1: img0}
        self._dir = +1

        self.image = self._imgs[self._dir]
        self.rect = self.image.get_rect()

        # 物理（ここは一切変更しない）
        self._vx = 0
        self._vy = 0.0
        self._speed = 8
        self._gravity = 0.85
        self._jump_v0 = -15
        self._jump_count = 0
        self._max_jump = 2

        self.rect.center = xy
        self.rect.bottom = get_ground_y()

    def try_jump(self) -> None:
        if self._jump_count < self._max_jump:
            self._vy = self._jump_v0
            self._jump_count += 1

    def update(self, key_lst: list[bool], screen: pg.Surface):
        self._vx = 0
        if key_lst[pg.K_LEFT]:
            self._vx = -self._speed
            self._dir = -1
        if key_lst[pg.K_RIGHT]:
            self._vx = +self._speed
            self._dir = +1

        self.rect.x += self._vx
        self.rect = clamp_in_screen(self.rect)

        self._vy += self._gravity
        self.rect.y += int(self._vy)

        gy = get_ground_y()
        if self.rect.bottom >= gy:
            self.rect.bottom = gy
            self._vy = 0.0
            self._jump_count = 0

        self.image = self._imgs[self._dir]
        screen.blit(self.image, self.rect)

    def get_rect(self) -> pg.Rect:
        return self.rect


class Enemy(pg.sprite.Sprite):
    """
    敵：右端から左へ流れる（ダミー：赤い矩形）
    """
    def __init__(self, stage: int):
        super().__init__()
        self._speed = stage_params(stage)["enemy_speed"]

        w = random.randint(40, 70)
        h = random.randint(40, 70)
        self.image = pg.Surface((w, h), pg.SRCALPHA)
        self.image.fill((230, 70, 70, 255))
        self.rect = self.image.get_rect()

        self.rect.left = WIDTH + random.randint(0, 160)
        self.rect.bottom = get_ground_y()

    def update(self):
        self.rect.x -= self._speed
        self.rect.bottom = get_ground_y()
        if self.rect.right < 0:
            self.kill()


# =========================
# メイン
# =========================
def main():
    pg.display.set_caption("こうかとん横スクロール（ベース）")
    screen = pg.display.set_mode((WIDTH, HEIGHT))
    clock = pg.time.Clock()

    stage = 1
    params = stage_params(stage)

    bg = Background(params["bg_file"], params["bg_speed"])
    bird = Bird(3, (200, get_ground_y()))
    enemies = pg.sprite.Group()

    # ===== 他の人のアイテムGroupを受け取る場所 =====
    # 統合するときは、次の1行を「相手が作った items（pg.sprite.Group）」に差し替えるだけでOK
    items = pg.sprite.Group()

    # ===== HP/Score/UI =====
    hp = HP_MAX
    score = 0
    font = pg.font.Font(None, 36)
    dmg_popup_tmr = 0
    inv_tmr = 0

    # ===== 右下UI（Attack/Status） =====
    current_attack: str | None = None
    current_status: str | None = None

    font_ui = pg.font.Font(None, 26)
    font_item = pg.font.Font(None, 22)

    attack_box = pg.Rect(
        WIDTH - (BOX_W * 2 + BOX_GAP) - BOX_MARGIN,
        HEIGHT - BOX_H - BOX_MARGIN,
        BOX_W, BOX_H
    )
    status_box = pg.Rect(
        WIDTH - BOX_W - BOX_MARGIN,
        HEIGHT - BOX_H - BOX_MARGIN,
        BOX_W, BOX_H
    )

    def read_item_info(it) -> tuple[str | None, str | None]:
        """
        他人実装の属性名ズレを吸収して (kind, name) を返す
        kind: "attack" or "status"
        name: 表示名
        """
        kind = None
        for k in ("kind", "type", "category"):
            v = getattr(it, k, None)
            if isinstance(v, str):
                kind = v.lower()
                break

        name = None
        for k in ("name", "item_name", "label"):
            v = getattr(it, k, None)
            if isinstance(v, str):
                name = v
                break

        if kind in ("atk", "attack_item"):
            kind = "attack"
        if kind in ("sts", "status_item"):
            kind = "status"

        return kind, name

    # ===== Score縁取り描画（追加）=====
    def draw_text_outline(surf: pg.Surface, text: str, font_: pg.font.Font, pos: tuple[int, int],
                          text_color: tuple[int, int, int], outline_color: tuple[int, int, int],
                          outline_px: int = 2) -> None:
        x, y = pos
        outline = font_.render(text, True, outline_color)
        for ox in range(-outline_px, outline_px + 1):
            for oy in range(-outline_px, outline_px + 1):
                if ox == 0 and oy == 0:
                    continue
                surf.blit(outline, (x + ox, y + oy))
        body = font_.render(text, True, text_color)
        surf.blit(body, (x, y))

    tmr = 0
    while True:
        key_lst = pg.key.get_pressed()

        for event in pg.event.get():
            if event.type == pg.QUIT:
                return 0
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_ESCAPE:
                    return 0
                if event.key == pg.K_UP:
                    bird.try_jump()

        # ステージ切替（全2ステージ）
        if stage == 1 and should_switch_stage(tmr):
            stage = 2
            params = stage_params(stage)
            bg = Background(params["bg_file"], params["bg_speed"])
            bird.get_rect().bottom = get_ground_y()

        # 敵生成：複数流入（変更なし）
        if tmr % params["spawn_interval"] == 0:
            spawn_enemy(enemies, stage)
            if random.random() < 0.30:
                spawn_enemy(enemies, stage)

        # ===== 描画（速度など変更なし）=====
        bg.update(screen)
        if DEBUG_DRAW_GROUND_LINE:
            pg.draw.line(screen, (0, 0, 0), (0, get_ground_y()), (WIDTH, get_ground_y()), 2)

        # 更新
        bird.update(key_lst, screen)
        enemies.update()
        items.update()  # ← 他の人のアイテム（右→左）は相手update内で動く想定

        # ===== 敵ダメージ（HP-20）=====
        if inv_tmr > 0:
            inv_tmr -= 1

        hit_list = pg.sprite.spritecollide(bird, enemies, False)
        if hit_list and inv_tmr == 0:
            hp = max(0, hp - DMG)

            if hp <= 0:
                return 0

            for e in hit_list:
                e.kill()

            dmg_popup_tmr = POPUP_FRAMES
            inv_tmr = INV_FRAMES

        # ===== アイテム取得（触れたら取得→右下表示を置き換え）=====
        got_items = pg.sprite.spritecollide(bird, items, True)  # True=拾ったら消える
        for it in got_items:
            kind, name = read_item_info(it)
            if kind == "attack":
                current_attack = name if name is not None else "Unknown"
            elif kind == "status":
                current_status = name if name is not None else "Unknown"

        # 描画（スプライト）
        items.draw(screen)
        enemies.draw(screen)

        # ===== UI：HP（左下）=====
        hp_pos = (20, HEIGHT - 50)
        hp_text = font.render(f"HP:{hp}", True, (255, 255, 255))
        screen.blit(hp_text, hp_pos)

        # HPバー（残りHPを緑）
        bar_x, bar_y = 20, HEIGHT - 25
        bar_w, bar_h = 200, 14
        pg.draw.rect(screen, (0, 0, 0), (bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4))
        pg.draw.rect(screen, (255, 255, 255), (bar_x, bar_y, bar_w, bar_h))
        hp_ratio = max(0, min(1, hp / HP_MAX))
        pg.draw.rect(screen, (0, 200, 0), (bar_x, bar_y, int(bar_w * hp_ratio), bar_h))

        # 「-20」赤表示（約2秒）
        if dmg_popup_tmr > 0:
            dmg_popup_tmr -= 1
            dmg_text = font.render(f"-{DMG}", True, (255, 0, 0))
            screen.blit(dmg_text, (hp_pos[0] + hp_text.get_width() + 10, hp_pos[1]))

        # ===== UI：Score（右上：白縁＋中黒）=====
        score_str = f"Score:{score}"
        tmp = font.render(score_str, True, (0, 0, 0))  # 幅取得用
        score_pos = (WIDTH - tmp.get_width() - 20, 20)
        draw_text_outline(screen, score_str, font, score_pos, (0, 0, 0), (255, 255, 255), outline_px=2)

        # ===== UI：右下 Attack / Status（黒塗り＋白枠）=====
        pg.draw.rect(screen, (0, 0, 0), attack_box)
        pg.draw.rect(screen, (255, 255, 255), attack_box, 2)
        pg.draw.rect(screen, (0, 0, 0), status_box)
        pg.draw.rect(screen, (255, 255, 255), status_box, 2)

        atk_label = font_ui.render("Attack", True, (255, 255, 255))
        sta_label = font_ui.render("Status", True, (255, 255, 255))
        screen.blit(atk_label, (attack_box.x + 10, attack_box.y + 8))
        screen.blit(sta_label, (status_box.x + 10, status_box.y + 8))

        atk_name = current_attack if current_attack is not None else "-"
        sta_name = current_status if current_status is not None else "-"
        atk_text = font_item.render(atk_name, True, (255, 255, 255))
        sta_text = font_item.render(sta_name, True, (255, 255, 255))
        screen.blit(atk_text, (attack_box.x + 12, attack_box.y + 40))
        screen.blit(sta_text, (status_box.x + 12, status_box.y + 40))

        pg.display.update()
        tmr += 1
        clock.tick(FPS)


if __name__ == "__main__":
    pg.init()
    main()
    pg.quit()
    sys.exit()
