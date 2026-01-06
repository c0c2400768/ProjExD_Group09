import os
import random
import math
import pygame as pg

os.chdir(os.path.dirname(os.path.abspath(__file__)))

WIDTH = 1100
HEIGHT = 650
FPS = 60
BEAM_IMG_OFFSET_DEG = 0
ARROW_IMG_OFFSET_DEG = -45

DEBUG_DRAW_GROUND_LINE = True

# =====================
# 初期値設定
# =====================

GROUND_Y = HEIGHT - 60
# ===== HP/ダメージ（追加）=====
HP_MAX = 100
DMG = 20.0
POPUP_FRAMES = 120   # 約2秒（60FPS想定）
KINOKO_HEAL = 20
# =====================
STATE_START = 0
STATE_PLAY = 1
STATE_TO_FINAL = 2
STATE_CLEAR = 3
STATE_GAMEOVER = 4
# ===== 右下UI（Attack/Status）（追加）=====
BOX_W, BOX_H = 220, 110
BOX_GAP = 14
BOX_MARGIN = 20
# ★ 足元補正値
FOOT_OFFSET_BIRD = 10
FOOT_OFFSET_BOSS = 8

FINAL_TRANSITION_FRAMES = POPUP_FRAMES 
FINAL_BOSS_SCORE = 1500
FINAL_BOSS_HP = 3000

# アイテムスポーン間隔(フレーム) と スポーン確率
ITEM_SPAWN_INTERVAL_STAGE1 = 90   # 1.5秒(60FPS想定)
ITEM_SPAWN_INTERVAL_STAGE2 = 70
ITEM_SPAWN_PROB_STAGE1 = 0.55
ITEM_SPAWN_PROB_STAGE2 = 0.65


# =========================
# 共通関数
# =========================
def load_font(size):
    return pg.font.SysFont("meiryo", size)

_IMAGE_CACHE: dict[str, pg.Surface] = {}

def load_image(filename: str) -> pg.Surface:


    if filename in _IMAGE_CACHE:
        return _IMAGE_CACHE[filename]
    candidates = [os.path.join("fig", filename), filename]
    for path in candidates:
        try:
            img = pg.image.load(path)
            if pg.display.get_init() and pg.display.get_surface() is not None:
                img = img.convert_alpha()
            _IMAGE_CACHE[filename] = img
            return img
        except:
            pass
    raise SystemExit(f"画像 {filename} の読み込みに失敗しました")

# =====================
# 画面描画(担当：江隈)
# =====================

def draw_start_screen(screen):
    """
    スタート画面（タイトル＋開始案内＋操作説明＋中ボス出現条件）を描画する。
    """
    screen.fill((0, 0, 0)) # 背景を黒で塗りつぶして前フレームの残像を消す

    # フォント（サイズは固定：タイトル/案内/本文）
    title_font = load_font(80)
    sub_font = load_font(40)
    body_font = load_font(24)

    # --- タイトル ---
    # 画面上部に固定配置（タイトルは中央寄せ）
    title = title_font.render("こうかとんダンジョン", True, (255, 255, 255))
    title_rect = title.get_rect(center=(WIDTH // 2, 110))
    screen.blit(title, title_rect)

    # --- スタート案内 ---
    # ENTERで開始することを示す（タイトル直下に中央寄せ）
    start = sub_font.render("ENTERでスタート", True, (200, 200, 200))
    start_rect = start.get_rect(center=(WIDTH // 2, 200))
    screen.blit(start, start_rect)

    # --- 説明文（下に収める） ---
    # 表示する文字列のリスト（空文字 "" は段落の空行として使う）
    lines = [
        "操作方法:",
        "  ←/→ : 移動",
        "  ↑   : ジャンプ（最大2段、アイテムで変化）",
        "  SPACE: 攻撃（攻撃アイテム所持時のみ）",
        "  ESC : 終了",
        "",
        "中ボス出現条件:",
        "  Score > 250 で中ボス出現（モブ敵は一旦消える）",
    ]

    x = 140  # 本文の左端X（読みやすいように左寄せで固定）
    line_gap = 28  # 1行ごとの縦間隔（フォントサイズ24に対し余白を含めた見やすい値）

    # タイトル＆案内の下から開始し、画面下に収める
    top_y = 260

    # もし行数が増えても下からはみ出しにくいように最大開始位置を制限
    total_h = (len(lines) - 1) * line_gap + body_font.get_height()
    max_top_y = HEIGHT - 20 - total_h
    y = min(top_y, max_top_y)

    # 行ごとに描画（左寄せ＋一定間隔）
    for i, line in enumerate(lines):
        screen.blit(body_font.render(line, True, (255, 255, 255)), (x, y + i * line_gap))

def draw_to_final_screen(screen):
    """
    ステージ遷移（最終ステージへ移動中）の案内画面を描画する。
    """
    screen.fill((0, 0, 0)) # 背景を黒で塗りつぶし、前フレームの描画をリセットする

    # フォント（サイズは固定：タイトル/本文）
    title_font = load_font(80)
    body_font = load_font(28)

    # --- タイトルは上寄せ（中央に置かない） ---
    title = title_font.render("最終ステージへ", True, (255, 255, 0))
    title_rect = title.get_rect(center=(WIDTH // 2, 150))
    screen.blit(title, title_rect)

    # FINAL_BOSS_SCORE / FINAL_BOSS_HP はゲーム側の定数と連動して表示する
    lines = [
        "最終ボス出現条件:",
        f"  最終ステージ中に Score {FINAL_BOSS_SCORE} 以上で出現",
        f"  最終ボスHP: {FINAL_BOSS_HP}",
    ]

    x = 220
    line_gap = 36

    # タイトルの“下端 + 余白”から本文開始
    y = title_rect.bottom + 40
    for i, line in enumerate(lines):
        screen.blit(body_font.render(line, True, (255, 255, 255)), (x, y + i * line_gap))

def draw_clear_screen(screen, score: int):
    """
    ゲームクリア画面を描画する。
    """
    screen.fill((0, 0, 0)) # 背景を黒で塗りつぶし、前フレームの描画を消す

    title_font = load_font(80)
    score_font = load_font(40)

    title = title_font.render("CLEAR", True, (0, 255, 0))
    score_surf = score_font.render(f"Score: {score}", True, (255, 255, 255))

    # 高さを測って“被らない間隔”で縦に並べる
    gap = 30
    total_h = title.get_height() + gap + score_surf.get_height()

    top = (HEIGHT - total_h) // 2
    title_rect = title.get_rect(center=(WIDTH // 2, top + title.get_height() // 2))
    score_rect = score_surf.get_rect(center=(WIDTH // 2, title_rect.bottom + gap + score_surf.get_height() // 2))

    screen.blit(title, title_rect)
    screen.blit(score_surf, score_rect)

def draw_gameover_screen(screen, score: int):
    """
    ゲームオーバー画面を描画する。
    """
    screen.fill((0, 0, 0)) # 背景を黒で塗りつぶし、前フレームの描画を消す

    title_font = load_font(80)
    score_font = load_font(40)

    title = title_font.render("GAME OVER", True, (255, 0, 0))
    score_surf = score_font.render(f"Score: {score}", True, (255, 255, 255))

    gap = 30
    total_h = title.get_height() + gap + score_surf.get_height()

    top = (HEIGHT - total_h) // 2
    title_rect = title.get_rect(center=(WIDTH // 2, top + title.get_height() // 2))
    score_rect = score_surf.get_rect(center=(WIDTH // 2, title_rect.bottom + gap + score_surf.get_height() // 2))

    screen.blit(title, title_rect)
    screen.blit(score_surf, score_rect)

# =================
# 画面描画ここまで
# =================

def clamp_in_screen(rect: pg.Rect) -> pg.Rect:
    """
    Rect（当たり判定用の四角形）が画面の外に出ないように、座標を補正する。
    """
    rect.left = max(0, rect.left)
    rect.right = min(WIDTH, rect.right)
    rect.top = max(0, rect.top)
    rect.bottom = min(HEIGHT, rect.bottom)
    return rect

def get_ground_y() -> int:
    """
    現在のステージにおける「地面のY座標」を返す。

    このプログラムでは地面の高さが固定ではなく、
    Background() を読み込むたびに detect_ground_y() で推定して GROUND_Y を更新する。
    """
    return GROUND_Y

def set_ground_y(v: int) -> None:
    """
    地面のY座標（GROUND_Y）を更新する。
    """
    global GROUND_Y
    GROUND_Y = v

def stage_params(stage: int) -> dict[str, int | str]:
    """
    ステージごとの設定

     Returns:
        dict[str, int | str]:
            "bg_file" (str): 背景画像ファイル名
            "bg_speed" (int): 背景スクロール速度
            "enemy_speed" (int): 敵の移動速度
            "item_speed" (int): アイテムの移動速度
            "spawn_interval" (int): 敵の生成間隔（フレーム）
    
    """
    if stage == 1:
        return {
            "bg_file": "bg_1.jpg",
            "bg_speed": 4,
            "enemy_speed": 5,
            "item_speed": 5,
            "spawn_interval": 60,  # フレーム間隔
        }
    return {
        "bg_file": "bg_2.jpg",
        "bg_speed": 4,
        "enemy_speed": 5,
        "item_speed": 7,
        "spawn_interval": 45,
    }

# ========================
# 敵スポーン関連関数(担当：高柳)
# ========================
def spawn_enemy(enemies: pg.sprite.Group, stage: int) -> None:
    """
    敵（Enemy）を1体スポーンして enemies グループに追加する。
    """
    params = stage_params(stage)
    kind = random.choice(["ground", "air"])  # 地面敵 / 空中敵
    enemies.add(Enemy(stage=stage, kind=kind, speed=params["enemy_speed"]))

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

# ========================
# 中ボス関連クラス(担当：稲葉)
# =========================

class Beam_tbos(pg.sprite.Sprite):
    """中ボスが放つビーム"""
    def __init__(self, pos: tuple[int, int]):
        super().__init__()
        raw_image = load_image("Beam_tbos.png")
        self.image = pg.transform.smoothscale(raw_image, (200, 80))
        self.rect = self.image.get_rect(center=pos)
        self._speed = 15

    def update(self):
        self.rect.x -= self._speed
        if self.rect.right < 0:
            self.kill()

class Meteor(pg.sprite.Sprite):
    """中ボスが降らせる隕石"""
    def __init__(self, target_x: int):
        super().__init__()
        size = random.randint(50, 150)
        raw_image = load_image("Meteor.png")
        self.image = pg.transform.smoothscale(raw_image, (size, size))
        self.rect = self.image.get_rect(center=(target_x, -50))
        self._speed_y = 6

    def update(self):
        self.rect.y += self._speed_y
        if self.rect.top > HEIGHT:
            self.kill()

class MidBoss(pg.sprite.Sprite):
    """
    中ボス：画面右側に滞在し、ビームと隕石で攻撃
    """
    def __init__(self):
        super().__init__()
        raw_image = load_image("Ramieru.png")
        self.image = pg.transform.smoothscale(raw_image, (300, 300))
        self.rect = self.image.get_rect()
        self.rect.center = (WIDTH - 150, get_ground_y() - 200)
        
        self._timer = 0
        self.hp = 1500

    def update(self, bird_rect: pg.Rect, beams_tbos: pg.sprite.Group, meteors: pg.sprite.Group):
        self._timer += 1

        # 【上下移動の計算】
        # math.sin を使うことで滑らかな波のような動きにする
        # 0.05 を変えると速さが、100 を変えると揺れ幅が変わる
        move_y = math.sin(self._timer * 0.05) * 100

        # 基準点（地面の高さ）を更新しつつ、計算した揺れを加算する
        self._base_y = get_ground_y() - 250
        self.rect.centery = self._base_y + move_y

        # ビーム発射（1.5秒に1回）
        if self._timer % 90 == 0:
            beams_tbos.add(Beam_tbos(self.rect.center))

        # 隕石落下（2秒に1回、こうかとんの頭上に降らす）
        if self._timer % 120 == 0:
            meteors.add(Meteor(bird_rect.centerx))

    def get_hp(self) -> int:
        return self.hp

# =========================
# ここまで
# =========================

class Background:
    def __init__(self, bg_file: str, speed: int):
        raw = load_image(bg_file)
        self._img = pg.transform.smoothscale(raw, (WIDTH, HEIGHT))
        self._speed = speed
        self._x1 = 0
        self._x2 = WIDTH
        set_ground_y(detect_ground_y(self._img))

    def update(self, screen):
        self._x1 -= self._speed
        self._x2 -= self._speed
        if self._x1 <= -WIDTH: self._x1 = self._x2 + WIDTH
        if self._x2 <= -WIDTH: self._x2 = self._x1 + WIDTH
        screen.blit(self._img, (self._x1, 0))
        screen.blit(self._img, (self._x2, 0))

    def get_speed(self) -> int:
        return self._speed

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
        self._vy = 0
        self._speed = 8
        self._gravity = 0.85
        self._jump_v0 = -15
        self._jump_count = 0
        self._max_jump = 2

        self.rect.center = xy
        self.rect.bottom = get_ground_y() + FOOT_OFFSET_BIRD

        # --- HP/無敵時間（追加） ---高柳
        self.hp = 100
        self._inv = 0   # 無敵フレーム（連続ダメ防止）

        self._damage_tmr = 0  # 追加：ダメージ点滅用タイマー

    def set_damage(self):
            #"""追加：ダメージを受けたときにタイマーをセットする"""
            self._damage_tmr = 30  # 30フレーム（約0.5秒）点滅させる

    def try_jump(self):
        if self._jump_count < self._max_jump:
            self._vy = self._jump_v0
            self._jump_count += 1

    def update(self, key_lst: list[bool], screen: pg.Surface) -> None:
        self._vx = 0
        if key_lst[pg.K_LEFT]:
            self._vx = -self._speed
            self._dir = -1
        if key_lst[pg.K_RIGHT]:
            self._vx = +self._speed*0.5
            self._dir = +1
        if self._inv > 0:
            self._inv -= 1


        self.rect.x += self._vx
        self.rect = clamp_in_screen(self.rect)

        self._vy += self._gravity
        self.rect.y += int(self._vy)

        gy = get_ground_y()
        if self.rect.bottom >= gy:
            self.rect.bottom = gy
            self._vy = 0.0
            self._jump_count = 0

        # 追加：ダメージ点滅ロジック
        if self._damage_tmr > 0:
            self._damage_tmr -= 1
            # 2フレームに1回描画しない時間を作ることで点滅させる
            if self._damage_tmr % 4 < 2:
                return # 描画せずに終了（点滅の「消える」瞬間）

        self.image = self._imgs[self._dir]
        screen.blit(self.image, self.rect)

    def get_rect(self) -> pg.Rect:
        return self.rect

    def set_max_jump(self, n: int) -> None:
        self._max_jump = max(1, int(n))

    def get_max_jump(self) -> int:
        return self._max_jump

    def get_speed(self) -> int:
        return self._speed
    
    def get_dir(self) -> int:
        """+1: 右向き, -1: 左向き"""
        return self._dir
    
    #高柳追加
    def take_damage(self, dmg: int) -> None:
        """無敵中でなければダメージを受ける"""
        if self._inv == 0:
            self.hp = max(0, self.hp - dmg)
            self._inv = 30  # 0.5秒くらい（60FPS想定）

    def get_vy(self) -> float:
        return self._vy

    def set_vy(self, v: float) -> None:
        self._vy = v

# ========================
# 敵スポーン関連関数(担当：高柳)
# ========================

class Enemy(pg.sprite.Sprite):
    """
    モブ敵（2パターン）
    - ground : 地面に沿って左へ流れる（ジャンプで踏める）
    - air    : 空中を左へ流れる（踏める）
    ステージ1: doragon1.png / gimen1.png
    ステージ2: doragon2.png / gimen2.png
    """
    def __init__(self, stage: int, kind: str = "ground", speed: int = 7):
        super().__init__()
        self.stage = stage
        self.kind = kind

        # ステージごとの画像を選ぶ（UFO/alienは使わない）
        if self.stage == 1:
            img_file = "enemy3.png" if self.kind == "ground" else "dagon.png"
        else:
            img_file = "enemy4.png" if self.kind == "ground" else "stennow.png"

        base = load_image(img_file)

        # サイズ調整（必要なら数字だけ変えてOK）
        scale = 0.05 if self.kind == "ground" else 0.05
        self.image = pg.transform.rotozoom(base, 0, scale)
        self.rect = self.image.get_rect()

        # 右端から左へ流れる（地面と平行）
        self.vx = -abs(speed)
        self.vy = 0
        self.rect.left = WIDTH + random.randint(0, 80)

        gy = get_ground_y()
        if self.kind == "ground":
            self.rect.bottom = gy
        else:
            y = gy - random.randint(120, 260)
            self.rect.bottom = max(40, y)

    def update(self):
        self.rect.move_ip(self.vx, self.vy)

        if (
            self.rect.right < -50 or
            self.rect.left > WIDTH + 50 or
            self.rect.top > HEIGHT + 50
        ):
            self.kill()

# ========================
# ボス関連クラス(担当：赤路)
# ========================

class Boss(pg.sprite.Sprite):

    def __init__(self):
        super().__init__()

        self.base_image = pg.transform.smoothscale(
            load_image("zerueru1.png"), (200, 200)
        )
        self.hit_image = self.base_image.copy()
        self.hit_image.fill((255, 80, 80), special_flags=pg.BLEND_RGBA_MULT)

        self.image = self.base_image
        self.rect = self.image.get_rect()
        self.rect.centerx = WIDTH // 2
        self.rect.bottom = get_ground_y() + FOOT_OFFSET_BOSS

        self._vx = random.choice([-4, 4])
        self._vy = 0
        self._gravity = 0.8
        self._jump_v0 = -14

        self._action_tmr = 0
        self._next_action = random.randint(60, 120)

        self.hit_timer = 0

        self.hp = FINAL_BOSS_HP

        self._shot_tmr = 0
        self._shot_interval = 90  # 1.5秒ごと

    def update(self, bird_rect: pg.Rect, boss_meteors: pg.sprite.Group):
        self._action_tmr += 1
        if self._action_tmr >= self._next_action:
            self._action_tmr = 0
            self._next_action = random.randint(60, 120)
            self._vx = random.choice([-4, 4])
            if random.random() < 0.4 and self.rect.bottom >= get_ground_y() + FOOT_OFFSET_BOSS:
                self._vy = self._jump_v0

        self.rect.x += self._vx
        if self.rect.left <= 80 or self.rect.right >= WIDTH - 80:
            self._vx *= -1

        self._vy += self._gravity
        self.rect.y += int(self._vy)

        if self.rect.bottom >= get_ground_y() + FOOT_OFFSET_BOSS:
            self.rect.bottom = get_ground_y() + FOOT_OFFSET_BOSS
            self._vy = 0

        if self.hit_timer > 0:
            self.hit_timer -= 1

        self.image = self.hit_image if self.hit_timer > 0 else self.base_image

        self._shot_tmr += 1
        if self._shot_tmr % self._shot_interval == 0:
            # こうかとんがボスの左にいるなら左へ、右なら右へ
            d = -1 if bird_rect.centerx < self.rect.centerx else +1

            # 発射位置（ボスの左右端から少し外）
            if d == -1:
                start = (self.rect.left - 20, self.rect.centery)
            else:
                start = (self.rect.right + 20, self.rect.centery)

            boss_meteors.add(SideMeteor(start, d))

    def on_hit(self):
        self.hit_timer = 10

    def draw(self, screen):
        screen.blit(self.image, self.rect)

class SideMeteor(pg.sprite.Sprite):
    """最終ボスが横向きに放つ隕石（Meteor.png流用）"""
    def __init__(self, start_xy: tuple[int, int], direction: int):
        super().__init__()
        size = random.randint(50, 150)
        raw_image = load_image("Meteor.png")
        self.image = pg.transform.smoothscale(raw_image, (size, size))
        self.rect = self.image.get_rect(center=start_xy)

        self._dir = +1 if direction >= 0 else -1
        self._vx = 14 * self._dir  # 速さ（好みで調整）

    def update(self):
        self.rect.x += self._vx
        if self.rect.right < 0 or self.rect.left > WIDTH:
            self.kill()  # kill() は所属している全Groupから外れる :contentReference[oaicite:1]{index=1}
            

# =========================
# ここまで
# =========================

class Explosion(pg.sprite.Sprite):
    """
    爆発エフェクト：中心で拡大縮小を繰り返しながら消滅
    """
    def __init__(self, center_xy: tuple[int, int], life: int = 30):
        super().__init__()
        img = load_image("explosion.gif")
        self._imgs = [img, pg.transform.flip(img, True, True)] # 拡大縮小用に2枚用意
        self.image = self._imgs[0]
        self.rect = self.image.get_rect(center=center_xy)
        self._life = life

    def update(self) -> None:
        self._life -= 1
        self.image = self._imgs[(self._life // 5) % 2] # 5フレームごとに切替
        if self._life <= 0:
            self.kill()

class Beam(pg.sprite.Sprite):
    """
    攻撃弾（ビーム）。

    仕様:
    - 発射位置から右方向へ直進
    - 画面外に出たら消滅
    """
    RANGE_PX = 200

    def __init__(self, start_xy: tuple[int, int], direction: int = +1):
        super().__init__()
        base = load_image("beam_k.png")

        self._dir = +1 if direction >= 0 else -1
        angle = (0 if self._dir == +1 else 180) + BEAM_IMG_OFFSET_DEG

        # 画像も向きに合わせる（回転の仕様：反時計回り、負で時計回り）:contentReference[oaicite:3]{index=3}
        self.image = pg.transform.rotozoom(base, angle, 1.0)
        self.rect = self.image.get_rect(center=start_xy)

        self._vx = 16 * self._dir
        self._end_x = self.rect.centerx + self.RANGE_PX * self._dir

    def update(self) -> None:
        self.rect.x += self._vx

        # 到達距離で消す（右なら left>=end、左なら right<=end）
        if self._dir == +1:
            if self.rect.left >= self._end_x:
                self.kill()
        else:
            if self.rect.right <= self._end_x:
                self.kill()

        # 念のため画面外でも消す
        if self.rect.right < 0 or self.rect.left > WIDTH:
            self.kill()

class Arrow(pg.sprite.Sprite):
    """
    矢：放物線を描きつつ右へ進む
    """
    def __init__(self, start_xy: tuple[int, int], direction: int = +1):
        super().__init__()
        self._base_image = load_image("arrow.png")
        self._dir = +1 if direction >= 0 else -1

        self._scale = 0.2
        self.image = pg.transform.rotozoom(self._base_image, ARROW_IMG_OFFSET_DEG, self._scale)
        self.rect = self.image.get_rect(center=start_xy)

        self._vx = 16 * self._dir
        self._vy = -10.5
        self._g = 0.6
        self._angle = None
        
    def update(self) -> None:
        self.rect.x += self._vx
        self._vy += self._g
        self.rect.y += int(self._vy)

        # 速度ベクトル(vx, vy)の向きに合わせる
        # angleは「反時計回りの度数」（負で時計回り） :contentReference[oaicite:2]{index=2}
        # yは下に増えるので -atan2(vy, vx) が自然 :contentReference[oaicite:3]{index=3}
        new_angle = -math.degrees(math.atan2(self._vy, self._vx)) + ARROW_IMG_OFFSET_DEG

        if self._angle is None or abs(new_angle - self._angle) > 1.0:
            self._angle = new_angle
            center = self.rect.center
            self.image = pg.transform.rotozoom(self._base_image, self._angle, self._scale)
            self.rect = self.image.get_rect(center=center)

        ground = get_ground_y()
        GROUND_HIT_MARGIN = 12  # 8〜20くらいで調整

        # ★上昇中は地面判定しない（地面に立って撃った瞬間の即死を防ぐ）
        if self._vy >= 0 and self.rect.bottom >= ground - GROUND_HIT_MARGIN:
            self.kill()

# =========================
# アイテム関連関数(担当：岩間)
# =========================

class ItemDef:
    """
    アイテムの“定義情報”を保持するクラス（スポーンや描画用）。

    Fields:
    - item_id: アイテム識別子（例: "Beam", "arrow", "kinoko", "tabaco"）
    - category: "attack" または "status"
    - img_file: 画像ファイル名
    - weight: 重み付き抽選で使う重み
    - scale: 描画倍率（Item生成時に適用）
    """
    def __init__(self, item_id: str, category: str, img_file: str, weight: int, scale: float = 1.0):
        self._item_id = item_id          # "Beam", "kinoko" など
        self._category = category        # "attack" or "status"
        self._img_file = img_file        # 画像ファイル名
        self._weight = weight
        self._scale = scale

    def get_item_id(self) -> str:
        return self._item_id

    def get_category(self) -> str:
        return self._category

    def get_img_file(self) -> str:
        return self._img_file
    
    def get_weight(self) -> int:
        return self._weight

    def get_scale(self) -> float:
        return self._scale

class Inventory:

    """
    プレイヤーの所持アイテム状態を管理する。

    仕様:
    - 攻撃アイテムは1つだけ保持（attackスロット）
    - 状態アイテムは1つだけ保持（statusスロット）
    - 同カテゴリで別 item_id を取得した場合は、後から取った方で置換する
    """
    def __init__(self, item_defs: dict[str, ItemDef]):
        self._defs = item_defs
        self._attack_id = None
        self._status_id = None

    def pickup_attack(self, item_id: str) -> None:
        self._attack_id = item_id

    def pickup_status_basic(self, item_id: str) -> None:
        self._status_id = item_id

    def clear_status(self) -> None:
        self._status_id = None

    def get_attack(self) -> str | None:
        return self._attack_id

    def get_status(self) -> str | None:
        return self._status_id
    
class Item(pg.sprite.Sprite):
    """
    画面右端から左へ流れるアイテム（取得対象）。

    - 画像は ItemDef に従って読み込む（scaleも適用）
    - 出現Xは右端外（WIDTH + 乱数）
    - 出現Yは「画面上限〜地面直上」の範囲でランダム
    - updateで左へ移動し、画面外に出たら消滅
    """
    def __init__(self, idef: ItemDef, stage: int):
        super().__init__()
        self._item_id = idef.get_item_id()
        self._category = idef.get_category()
        self._speed = stage_params(stage)["item_speed"]

        img = load_image(idef.get_img_file())
        if idef.get_scale() != 1.0:
            img = pg.transform.rotozoom(img, 0, idef.get_scale())
        self.image = img
        self.rect = self.image.get_rect()

        self.rect.left = WIDTH + random.randint(0, 200)

        # 地面より上のどこかに出す
        gy = get_ground_y()
        margin = 10
        lowest = gy - (self.rect.height // 2) - margin   # これより下に出さない
        highest = max(60,self.rect.height // 2 + margin)                                     # これより上に出さない（画面上部）

        if highest > lowest:
            self.rect.centery = (highest + lowest) // 2
        else:
            self.rect.centery = random.randint(highest, lowest)


    def update(self) -> None:
        self.rect.x -= self._speed
        if self.rect.right < 0:
            self.kill()

    def get_item_id(self) -> str:
        return self._item_id

    def get_category(self) -> str:
        return self._category

def pick_weighted_item_id(item_defs: dict[str, ItemDef], stage: int) -> str:
    """
    item_defs の weight に基づいて item_id を1つ返す（重み付き抽選）。

    Args:
        item_defs: item_id -> ItemDef の辞書
        stage: 現状は抽選ロジックに影響しないが、将来ステージ別抽選に拡張できるため引数として保持

    Returns:
        str: 抽選された item_id
    """
    ids = list(item_defs.keys())
    weights = [max(0, item_defs[i].get_weight()) for i in ids]
    total = sum(weights)
    if total <= 0:
        # 全部0なら先頭
        return ids[0]

    r = random.randint(1, total)
    acc = 0
    for i, w in zip(ids, weights):
        acc += w
        if r <= acc:
            return i
    return ids[-1]

def maybe_spawn_item(tmr: int, stage: int, item_defs: dict[str, ItemDef], items: pg.sprite.Group) -> None:
    """
    アイテムをスポーンするかを判定し、スポーンする場合は items に追加する。

    - stage に応じてスポーン間隔(interval)と確率(prob)を切り替える
    - tmr が interval の倍数のタイミングのみ抽選する
    - 当選したら重み付き抽選で item_id を選ぶ
    """
    if stage == 1:
        interval = ITEM_SPAWN_INTERVAL_STAGE1
        prob = ITEM_SPAWN_PROB_STAGE1
    else:
        interval = ITEM_SPAWN_INTERVAL_STAGE2
        prob = ITEM_SPAWN_PROB_STAGE2

    if tmr % interval != 0:
        return

    if random.random() > prob:
        return

    item_id = pick_weighted_item_id(item_defs, stage)
    items.add(Item(item_defs[item_id], stage))
    
def apply_status_pickup(item_id: str, inv: Inventory, bird: Bird) -> None:
    """
    状態アイテム取得時の特殊ルールを適用する。

    仕様:
    - tabaco：所持中は二段ジャンプ不可（max_jump=1）
    - kinoko：
        - 無状態で取得 -> max_jump=3（状態は kinoko）
        - tabaco所持中に取得 -> tabacoを打ち消し無状態へ（max_jump=2）
        - kinoko所持中に取得 -> HP20回復（最大HPを超えない）

    副作用:
    - inv の状態スロット（status）を書き換える
    - bird の最大ジャンプ回数を変更する
    """
    cur_status = inv.get_status()

    if item_id == "tabaco":
        inv.pickup_status_basic("tabaco")
        bird.set_max_jump(1)
        return

    if item_id == "kinoko":
        if cur_status == "tabaco":
            # 打ち消し：無状態へ戻す
            inv.clear_status()
            bird.set_max_jump(2)
            return
        if cur_status == "kinoko":
            # ★追加：kinoko状態でkinokoを拾ったらHP回復
            bird.hp = min(HP_MAX, bird.hp + KINOKO_HEAL)
            # 状態はそのまま維持（明示的に再設定してもOK）
            inv.pickup_status_basic("kinoko")
            bird.set_max_jump(3)
            return
    
        inv.pickup_status_basic("kinoko")
        bird.set_max_jump(3)
        return

    # 他の状態アイテムが増えたらここに追加
    inv.pickup_status_basic(item_id)

def apply_status_from_current(inv: Inventory, bird: Bird) -> None:
    """
    ステージ切替などで、現在の所持状態に合わせてジャンプ数を再適用したい場合用
    """
    st = inv.get_status()
    if st == "tabaco":
        bird.set_max_jump(1)
    elif st == "kinoko":
        bird.set_max_jump(3)
    else:
        bird.set_max_jump(2)

# =========================
# メイン
# =========================
def main():
    pg.display.set_caption("こうかとんダンジョン")
    screen = pg.display.set_mode((WIDTH, HEIGHT))
    clock = pg.time.Clock()

    # ---- フォント ----
    font = load_font(32)
    font_ui = load_font(22)
    font_item = load_font(22)

    # ---- 状態 ----
    game_state = STATE_START
    state_timer = 0

    # ---- ステージ ----
    stage = 1
    params = stage_params(stage)
    bg = Background(params["bg_file"], params["bg_speed"])

    # ---- プレイヤー ----
    bird = Bird(3, (200, get_ground_y()))
    bird.hp = HP_MAX  # HPをbird.hpに統一

    # ---- スコア ----
    score = 0

    # ---- グループ ----
    enemies = pg.sprite.Group()
    items = pg.sprite.Group()
    beams = pg.sprite.Group()
    arrows = pg.sprite.Group()
    exps = pg.sprite.Group()

    midboss_group = pg.sprite.Group()
    boss_meteors = pg.sprite.Group()
    finalboss_group = pg.sprite.Group()
    beams_tbos = pg.sprite.Group()
    meteors = pg.sprite.Group()

    # ---- アイテム定義（ファイル名は要調整）----
    ITEM_DEFS = {
        "Beam": ItemDef("Beam", "attack", "beam_k.png", 6, scale=0.7),
        "arrow": ItemDef("arrow", "attack", "arrow.png", 6, scale=0.2),
        "kinoko": ItemDef("kinoko", "status", "kinoko.png", 3, scale=0.1),
        "tabaco": ItemDef("tabaco", "status", "tabaco.png", 3, scale=0.025),
    }
    inv = Inventory(ITEM_DEFS)

    # ---- 右下UI枠 ----(担当：佐藤)
    attack_box = pg.Rect(
        WIDTH - BOX_MARGIN - (BOX_W * 2 + BOX_GAP),  # 右端から「2箱+隙間」ぶん左へ
        HEIGHT - BOX_MARGIN - BOX_H,                 # 下端から1箱ぶん上へ
        BOX_W, BOX_H
    )
    status_box = pg.Rect(
        WIDTH - BOX_MARGIN - BOX_W,                  # 右端に寄せる
        HEIGHT - BOX_MARGIN - BOX_H,
        BOX_W, BOX_H
)

    # ---- UIアイコン（アイテム画像を流用）----(担当：佐藤)
    UI_ICONS = {}
    for k, idef in ITEM_DEFS.items():
        try:
            icon = load_image(idef.get_img_file())
            icon = pg.transform.smoothscale(icon, (40, 40))
            UI_ICONS[k] = icon
        except:
            # ファイル不一致の場合はダミー（落とさない）
            surf = pg.Surface((40, 40))
            surf.fill((80, 80, 80))
            UI_ICONS[k] = surf

    # ---- 中ボス管理 ----
    tmr = 0
    mid_boss_spawned = False
    mid_boss_defeated = False
    last_score = None
    score_surf = None
    score_pos = (0, 0)

    def make_outlined_text(font, text, text_color, outline_color, outline_px=2):
        base = font.render(text, True, text_color)
        w, h = base.get_width() + outline_px*2, base.get_height() + outline_px*2
        surf = pg.Surface((w, h), pg.SRCALPHA)
        for dx in range(-outline_px, outline_px + 1):
            for dy in range(-outline_px, outline_px + 1):
                if dx == 0 and dy == 0:
                    continue
                surf.blit(font.render(text, True, outline_color), (dx + outline_px, dy + outline_px))
        surf.blit(base, (outline_px, outline_px))
        return surf
    
    state_timer = 0

    mid_boss_spawned = False
    mid_boss_defeated = False

    final_stage = False
    final_boss_spawned = False
    final_boss_defeated = False

    while True:
        key_lst = pg.key.get_pressed()

        for event in pg.event.get():
            if event.type == pg.QUIT:
                return

            if event.type == pg.KEYDOWN:
                if game_state == STATE_START:
                    if event.key == pg.K_RETURN:
                        game_state = STATE_PLAY
                        tmr = 0
                        bird.hp = HP_MAX
                        enemies.empty()
                        items.empty()
                        beams.empty()
                        arrows.empty()
                        exps.empty()
                        midboss_group.empty()
                        beams_tbos.empty()
                        meteors.empty()
                        boss_meteors.empty()
                        mid_boss_spawned = False
                        mid_boss_defeated = False

                elif game_state == STATE_PLAY:
                    if event.key == pg.K_UP:
                        bird.try_jump()
                    if event.key == pg.K_ESCAPE:
                        return
                    if event.key == pg.K_SPACE:
                        atk_id = inv.get_attack()
                        d = bird.get_dir()  # +1 or -1

                        # 発射位置：右向きなら右手、左向きなら左手
                        if d == +1:
                            start = (bird.get_rect().right + 30, bird.get_rect().centery)
                        else:
                            start = (bird.get_rect().left - 30, bird.get_rect().centery)

                        if atk_id == "Beam":
                            beams.add(Beam(start, direction=d))
                        elif atk_id == "arrow":
                            arrows.add(Arrow(start, direction=d))

        # ---------- 描画クリア ----------
        screen.fill((0, 0, 0))

        # ---------- 状態別 ----------
        if game_state == STATE_START:
            draw_start_screen(screen)

        elif game_state == STATE_PLAY:
            # 背景 & 地面
            bg.update(screen)
            if DEBUG_DRAW_GROUND_LINE:
                pg.draw.line(screen, (0, 0, 0), (0, get_ground_y()), (WIDTH, get_ground_y()), 2)

            # --- 更新 ---
            bird.update(key_lst, screen)
            enemies.update()
            items.update()
            beams.update()
            arrows.update()
            exps.update()
            boss_meteors.update()

            # --- 敵スポーン（中ボス前だけ）---
            if (not mid_boss_spawned) and (not final_boss_spawned):
                spawn_interval = params["spawn_interval"]
                spawn_prob = 0.93  # ステージ1の基準

                # 最終ステージは「第一ステージより少し多め」
                if stage == 2:
                    spawn_interval = max(20, int(spawn_interval * 0.8))  # 間隔を短くして増やす
                    spawn_prob = 0.96                                   # 確率も少し上げる

                if tmr % spawn_interval == 0 and random.random() < spawn_prob:
                    spawn_enemy(enemies, stage)

            # --- 中ボス出現条件 ---
            if score > 250 and (not mid_boss_spawned) and (not mid_boss_defeated):
                mid_boss_spawned = True
                enemies.empty()
                midboss_group.add(MidBoss())

            # --- 最終Boss出現条件（最終ステージ中 && Score 1500到達）---
            if final_stage and (not final_boss_spawned) and (not final_boss_defeated) and score >= FINAL_BOSS_SCORE:
                final_boss_spawned = True

                enemies.empty()  # モブ消す（要件：出現止まる＋邪魔なら消す）
                beams.empty()
                arrows.empty()

                b = Boss()
                b.hp = FINAL_BOSS_HP
                finalboss_group.add(b)

            # --- アイテムスポーン ---
            maybe_spawn_item(tmr, stage, ITEM_DEFS, items)

            # 中ボス更新
            if mid_boss_spawned and len(midboss_group.sprites()) > 0:
                midboss_group.update(bird.get_rect(), beams_tbos, meteors)
                beams_tbos.update()
                meteors.update()

            # --- 当たり判定：攻撃 → 敵 ---
            hit1 = pg.sprite.groupcollide(enemies, beams, True, True)
            for emy in hit1.keys():
                exps.add(Explosion(emy.rect.center, life=30))
                score += random.randint(10, 20)

            hit2 = pg.sprite.groupcollide(enemies, arrows, True, True)
            for emy in hit2.keys():
                exps.add(Explosion(emy.rect.center, life=30))
                score += random.randint(10, 20)

            # --- 当たり判定：アイテム取得 ---
            picked = pg.sprite.spritecollide(bird, items, True)
            for it in picked:
                item_id = it.get_item_id()
                cat = ITEM_DEFS[item_id].get_category()
                if cat == "attack":
                    inv.pickup_attack(item_id)
                else:
                    apply_status_pickup(item_id, inv, bird)

            # --- 当たり判定：敵接触ダメージ（HPはbirdに統一）---
            if pg.sprite.spritecollide(bird, enemies, False):
                bird.take_damage(DMG)
                bird.set_damage()  # 点滅
                # 接触してる敵は消す（好みで）
                for e in pg.sprite.spritecollide(bird, enemies, True):
                    pass

            # --- 当たり判定：中ボス攻撃物 ---
            if pg.sprite.spritecollide(bird, beams_tbos, True):
                bird.take_damage(DMG)
                bird.set_damage()
            if pg.sprite.spritecollide(bird, meteors, True):
                bird.take_damage(DMG)
                bird.set_damage()
            if pg.sprite.spritecollide(bird, boss_meteors, True):
                bird.take_damage(DMG)
                bird.set_damage()

            if mid_boss_spawned and len(midboss_group.sprites()) > 0:
                boss = midboss_group.sprites()[0]
                if bird.get_rect().colliderect(boss.rect):
                    before = bird.hp
                    bird.take_damage(DMG)   # DMG=20.0 なので20ダメージ
                    if bird.hp < before:
                        bird.set_damage()

            # --- 中ボスに攻撃命中 ---
            if mid_boss_spawned and len(midboss_group.sprites()) > 0:
                boss = midboss_group.sprites()[0]
                hit_beams = pg.sprite.spritecollide(boss, beams, True)
                if hit_beams:
                    boss.hp -= 100 * len(hit_beams)

                hit_arrows = pg.sprite.spritecollide(boss, arrows, True)
                if hit_arrows:
                    boss.hp -= 80 * len(hit_arrows)

                # 撃破
                if boss.hp <= 0:
                    exps.add(Explosion(boss.rect.center, life=60))
                    midboss_group.empty()
                    beams_tbos.empty()
                    meteors.empty()
                    mid_boss_spawned = False
                    mid_boss_defeated = True
                    score += 1000
                    game_state = STATE_TO_FINAL
                    state_timer = 0
                    midboss_group.empty()
                    beams_tbos.empty()
                    meteors.empty()
                    enemies.empty()
                    items.empty()
                    beams.empty()
                    arrows.empty()
                    exps.empty()

                    mid_boss_spawned = False
                    mid_boss_defeated = True
                    final_stage = True

            # --- 当たり判定：最終ボス接触（ダメージ + ノックバック）---
            if final_boss_spawned and len(finalboss_group.sprites()) > 0:
                boss = finalboss_group.sprites()[0]

                if bird.get_rect().colliderect(boss.rect):
                    # ダメージ（無敵中なら take_damage 内で無効化される）
                    before = bird.hp
                    bird.take_damage(DMG)

                    # 実際にHPが減ったフレームだけ、ノックバックさせる（無敵中の連打防止）
                    if bird.hp < before:
                        bird.set_damage()

                        # 押し出し方向：こうかとんがボスの左なら左へ、右なら右へ
                        if bird.get_rect().centerx < boss.rect.centerx:
                            bird.rect.right = boss.rect.left - 2
                            bird.rect.x -= 24      # 横ノックバック量（好みで）
                        else:
                            bird.rect.left = boss.rect.right + 2
                            bird.rect.x += 24

                        # 上にも少し跳ねさせる（ふわっと感）
                        bird.set_vy(-10)

                        # 画面外に出ないように補正
                        bird.rect = clamp_in_screen(bird.rect)

            if final_boss_spawned and len(finalboss_group.sprites()) > 0:
                finalboss_group.update(bird.get_rect(), boss_meteors)

                boss = finalboss_group.sprites()[0]

                hit_beams = pg.sprite.spritecollide(boss, beams, True)
                if hit_beams:
                    boss.hp -= 100 * len(hit_beams)
                    boss.on_hit()

                hit_arrows = pg.sprite.spritecollide(boss, arrows, True)
                if hit_arrows:
                    boss.hp -= 80 * len(hit_arrows)
                    boss.on_hit()

                if boss.hp <= 0:
                    exps.add(Explosion(boss.rect.center, life=60))
                    finalboss_group.empty()
                    final_boss_defeated = True
                    final_boss_spawned = False
                    game_state = STATE_CLEAR

            # --- 描画 ---
            enemies.draw(screen)
            items.draw(screen)
            beams.draw(screen)
            arrows.draw(screen)
            exps.draw(screen)
            boss_meteors.draw(screen)

            # --- UI：左下HP ---(担当：佐藤)
            bar_x, bar_y = 20, HEIGHT - 25
            bar_w, bar_h = 200, 14

            hp_surf = font.render(f"HP:{bird.hp}", True, (255, 255, 255))
            hp_pos = (bar_x, bar_y - hp_surf.get_height() - 6)  # ← ゲージの上に6px余白
            screen.blit(hp_surf, hp_pos)

            pg.draw.rect(screen, (255, 255, 255), (bar_x, bar_y, bar_w, bar_h))
            ratio = max(0.0, min(1.0, bird.hp / HP_MAX))
            pg.draw.rect(screen, (0, 200, 0), (bar_x, bar_y, int(bar_w * ratio), bar_h))

            # --- UI：右上Score（縁取り）---(担当：佐藤)
            if score != last_score:
                last_score = score
                score_str = f"Score:{score}"
                score_surf = make_outlined_text(font, score_str, (255,255,255), (0,0,0), outline_px=2)
                score_pos = (WIDTH - score_surf.get_width() - 20, 20)

            screen.blit(score_surf, score_pos)

            # --- UI：右下 Attack/Status ---(担当：佐藤)
            pg.draw.rect(screen, (0, 0, 0), attack_box)
            pg.draw.rect(screen, (255, 255, 255), attack_box, 2)
            pg.draw.rect(screen, (0, 0, 0), status_box)
            pg.draw.rect(screen, (255, 255, 255), status_box, 2)

            screen.blit(font_ui.render("Attack", True, (255, 255, 255)), (attack_box.x + 10, attack_box.y + 8))
            screen.blit(font_ui.render("Status", True, (255, 255, 255)), (status_box.x + 10, status_box.y + 8))

            atk_id = inv.get_attack()
            sta_id = inv.get_status()

            def draw_slot(box, item_id):
                pad_x = 12
                top_y = box.y + 34
                area = pg.Rect(box.x + pad_x, top_y, box.w - pad_x * 2, box.h - (top_y - box.y) - 10)
                if item_id is None:
                    screen.blit(font_item.render("-", True, (255, 255, 255)), (area.x, area.y + 10))
                    return
                icon = UI_ICONS.get(item_id)
                icon_y = area.y + (area.h - icon.get_height()) // 2
                screen.blit(icon, (area.x, icon_y))
                name_x = area.x + icon.get_width() + 10
                screen.blit(font_item.render(str(item_id), True, (255, 255, 255)), (name_x, area.y + 10))

            draw_slot(attack_box, atk_id)
            draw_slot(status_box, sta_id)

            if mid_boss_spawned:
                midboss_group.draw(screen)
                beams_tbos.draw(screen)
                meteors.draw(screen)
                # 中ボスHP表示
                if len(midboss_group.sprites()) > 0:
                    boss = midboss_group.sprites()[0]
                    hp_txt = font.render(f"HP:{boss.hp}", True, (255, 255, 255))
                    screen.blit(hp_txt, (boss.rect.centerx - hp_txt.get_width() // 2, boss.rect.top - 30))

            if final_boss_spawned:
                finalboss_group.draw(screen)
                # 最終ボスHP表示
                if len(finalboss_group.sprites()) > 0:
                    boss = finalboss_group.sprites()[0]
                    hp_txt = font.render(f"HP:{boss.hp}", True, (255, 255, 255))
                    screen.blit(hp_txt, (boss.rect.centerx - hp_txt.get_width() // 2, boss.rect.top - 30))

            # --- ゲームオーバー判定 ---
            if bird.hp <= 0:
                game_state = STATE_GAMEOVER

            # ★tmrはPLAY中に進める
            tmr += 1

        elif game_state == STATE_TO_FINAL:
            draw_to_final_screen(screen)
            state_timer += 1

            if state_timer >= FINAL_TRANSITION_FRAMES:
                # ---- 最終ステージへ切り替え（背景＆敵種類変更）----
                stage = 2  # stage_params(2) を “最終ステージ用” として使う前提
                params = stage_params(stage)
                bg = Background(params["bg_file"], params["bg_speed"])

                # ここで地面が変わるので、足元合わせ直し
                bird.get_rect().bottom = get_ground_y()
                apply_status_from_current(inv, bird)

                # 最終ボス関連を初期化
                final_boss_spawned = False
                final_boss_defeated = False
                finalboss_group.empty()

                # PLAY に戻す
                game_state = STATE_PLAY
                state_timer = 0

            # --- ゲームオーバー判定 ---
            if bird.hp <= 0:
                game_state = STATE_GAMEOVER

            tmr += 1

        elif game_state == STATE_CLEAR:
            draw_clear_screen(screen, score)

        elif game_state == STATE_GAMEOVER:
            draw_gameover_screen(screen, score)

        pg.display.update()
        clock.tick(FPS)
if __name__ == "__main__":
    pg.init()
    main()
    pg.quit()
