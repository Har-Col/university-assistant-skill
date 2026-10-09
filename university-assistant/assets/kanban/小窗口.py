# -*- coding: utf-8 -*-
"""桌面小组件：深色极简 · 上下两张圆角卡片（课表 / 待办）。

- 顶部卡片：最上面一行日期标题横跨整行，下面左右两栏，中间一条垂直细分隔线
  - 左栏：今日课程（蓝色时间标签 + 白字）+ 明日预览（浅灰，不抢焦点）
  - 右栏：本周周期任务（只有一个复选框：勾上 = 记一次 +1，取消 = -1）
  - 日期标题右边还有一条「今晚有没有晚修」，有晚课就没有晚修
- 待办卡片：标题右边三个分类按钮（近期 / 月度 / 中期），只显示选中的那一组；
  每条两行（加粗标题 + 缩进浅灰备注），临近截止标橙，已完成沉到组底
- 待办条目的勾选直接写回 待办清单.md 的 - [ ] / - [x]，勾完变浅灰加删除线
- 周期任务不在下方待办列表里重复出现（已经搬到顶部卡片右栏），
  只动 看板数据.json 的 recurring_state，不碰 md
- 界面上只留「今天有晚修 / 今天没晚修」这两个表情，其余 emoji 一律不用

数据来自 _工具\\看板数据.json（由 生成看板.py 产出）。全部用 Canvas 手绘，方便做圆角。
"""

import os
import sys
import json
import ctypes
import subprocess
import tkinter as tk
from datetime import date, timedelta

# 工作区根目录：默认 = 本脚本所在目录的上一级（脚本放在 <工作区>\_工具\ 下）。
# 工作区搬到别处也不用改。要和 生成看板.py 里的 ROOT 指向同一个地方。
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "_工具")
DATA = os.path.join(TOOLS, "看板数据.json")
PREFS = os.path.join(TOOLS, "小窗口设置.json")
TODO_MD = os.path.join(ROOT, "待办清单.md")
HTML = os.path.join(ROOT, "看板.html")
GEN = os.path.join(TOOLS, "生成看板.py")
# 重新生成 / 重启自己时用哪个 Python：用「当前这个解释器」，别写死路径。
PY = sys.executable

# 透明键色：两套主题共用。必须是界面里绝不会用到的颜色，否则那块会被抠成透明。
KEY = "#0d0e10"

# 两套配色。切换主题时 apply_theme() 会把下面那些模块级名字重新绑定 ——
# 代码里所有 fill=XXX 都是调用时才去读的，所以不用逐处改。
THEMES = {
    "dark": {
        "WIN": "#131418",      # 窗口底（压暗一点，卡片才浮得起来）
        "CARD1": "#1f2b3d",    # 课表卡片：偏蓝
        "CARD2": "#202127",    # 待办卡片：中性灰
        "SHADOW": "#090a0d",   # 卡片下的轻微阴影（要比窗口底深，且不能等于 KEY）
        "LINE1": "#2a3646", "LINE2": "#2c2d34",
        "FG": "#f2f4f7", "DIM": "#8b93a0", "FAINT": "#565c66", "TINY": "#4e545d",
        "ACC": "#4c9aff", "ORANGE": "#ff9f45", "GREEN": "#5fd08a", "RED": "#ff6b6b",
        "TAB_OFF": "#4a505a",  # 未选中 Tab 的下划线
        "ON_ACC": "#0a1520",   # 压在蓝色块上的字（时间标签、勾号）
        "HOVER": "#ffffff",    # 悬停时点亮成什么颜色
        "done_fg": 0.66, "done_box": 0.55,
    },
    "light": {
        "WIN": "#eef0f3",
        "CARD1": "#e3ecfb",
        "CARD2": "#ffffff",
        "SHADOW": "#d5d9e0",
        "LINE1": "#b9cbe4", "LINE2": "#e6e9ee",
        "FG": "#14161b", "DIM": "#5f6672", "FAINT": "#8b93a0", "TINY": "#98a0ad",
        "ACC": "#0a5cff", "ORANGE": "#c96a12", "GREEN": "#128a4b", "RED": "#d93025",
        "TAB_OFF": "#b9c0cb",
        "ON_ACC": "#ffffff",
        "HOVER": "#000000",
        "done_fg": 0.70, "done_box": 0.55,
    },
    # 橡木 / 绿植 / 金属：深色木底，绿植当主色，金属只用在分隔线和不活跃的细节上
    "oak": {
        "WIN": "#17130f",      # 窗口底：深胡桃木
        "CARD1": "#241b12",    # 课表卡：深橡木（暖棕，和待办卡拉开色差）
        "CARD2": "#201c18",    # 待办卡：深炭（中性偏暖）
        "SHADOW": "#0d0a08",   # 阴影：比窗口底更深，但不能等于 KEY
        "LINE1": "#4d4840",    # 分隔线：冷一点的金属灰，压在木色上才像金属
        "LINE2": "#2c2721",
        "FG": "#efe7d8",       # 正文：浅橡木白
        "DIM": "#a89d8a",
        "FAINT": "#7b7264",
        "TINY": "#6c6459",
        "ACC": "#5fb97c",      # 主色：绿植（灯下的叶子绿，深底上要够亮）
        "ORANGE": "#e39a50",   # 紧急：陶土琥珀
        "GREEN": "#a8d06a",    # 今天没晚修：嫩叶黄绿（和主色分得开）
        "RED": "#f0736b",      # 放弃键悬停
        "TAB_OFF": "#6e6c64",  # 未选中 Tab 下划线：金属灰
        "ON_ACC": "#0c1f14",   # 压在绿块上的字：近黑的墨绿
        "HOVER": "#ffffff",
        "done_fg": 0.62, "done_box": 0.55,
    },
}
THEME = "dark"
THEME_ORDER = ("dark", "light", "oak")      # 底部按钮按这个顺序循环
THEME_LABEL = {"dark": "深色", "light": "白底", "oak": "橡木"}

STATE_KEY = "recurring_state"      # 周期任务进度，存在 看板数据.json 里

GAP_CARD = 24          # 卡片之间的间距
URGENT_DAYS = 3        # 距今 ≤ 3 天算「临近截止」，才标橙

UI = "Microsoft YaHei UI"
BASE_W, BASE_H = 336, 480
MIN_W = 360            # 最小宽度：再窄下去「时间标签 + 课程名」会压到中间的分隔线
R_WIN = 14
R_CARD = 12


def blend(c1, c2, t):
    """把 c1 往 c2 混 t（0~1）。Tk 画布没有逐元素透明度，用混色来模拟。"""
    try:
        a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
        return "#%02x%02x%02x" % tuple(
            int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))
    except Exception:
        return c1


def apply_theme(name):
    """切换配色。所有 fill=XXX 都是调用时才读模块变量，这里重新绑定就够了。"""
    global THEME, WIN, CARD1, CARD2, SHADOW, LINE1, LINE2, FG, DIM, FAINT, TINY
    global ACC, ORANGE, GREEN, RED, TAB_OFF, ON_ACC, HOVER, DONE_FG, DONE_BOX
    if name not in THEMES:
        name = "dark"
    THEME = name
    t = THEMES[name]
    WIN, CARD1, CARD2, SHADOW = t["WIN"], t["CARD1"], t["CARD2"], t["SHADOW"]
    LINE1, LINE2 = t["LINE1"], t["LINE2"]
    FG, DIM, FAINT, TINY = t["FG"], t["DIM"], t["FAINT"], t["TINY"]
    ACC, ORANGE, GREEN, RED = t["ACC"], t["ORANGE"], t["GREEN"], t["RED"]
    TAB_OFF, ON_ACC, HOVER = t["TAB_OFF"], t["ON_ACC"], t["HOVER"]
    # 已完成条目的「降低透明度」：把前景色往卡片底色混（两套主题的比例不一样）
    DONE_FG = blend(FG, CARD2, t["done_fg"])
    DONE_BOX = blend(ACC, CARD2, t["done_box"])


apply_theme("dark")

# 待办卡片顶部的三个分类按钮（顺序即显示顺序，第一个是默认选中项）
TABS = ("近期任务", "月度任务", "中期任务")


def enable_dpi():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def time_range(c):
    """一节课的时间标签。有下课时间就写「07:40-09:20」，缺了就只写上课时间。"""
    t = (c.get("time") or "").strip()
    e = (c.get("end") or "").strip()
    return "%s-%s" % (t, e) if (t and e) else t


def week_key(d):
    y, w, _ = d.isocalendar()
    return (y, w)


def week_count(dates, today):
    """这一周（周一起算）打过几次卡。跨周自动归零，因为只数本周的日期。"""
    k = week_key(today)
    n = 0
    for ds in (dates or []):
        try:
            if week_key(date.fromisoformat(str(ds))) == k:
                n += 1
        except Exception:
            pass
    return n


def done_today(dates, today):
    t = today.isoformat()
    return any(str(ds) == t for ds in (dates or []))


def tab_of(section):
    """把 待办清单.md 里的三级标题归到三个分类按钮上。

    对应关系（2026-09-21 时点）：
      近期任务 ←「有时效的，先做」
      月度任务 ←「可以排在本月的」
      中期任务 ←「中期：2 个月内（10 月中 — 11 月中）」

    只认关键词，所以 md 里改标题没关系，留一个能认出来的词就行。
    认不出来的分组一律落到「近期任务」——宁可放错位置，也不要把条目弄丢。
    """
    s = section or ""
    if "中期" in s:
        return "中期任务"
    if "本月" in s or "月度" in s:
        return "月度任务"
    return "近期任务"


def todo_rank(t):
    """0 = 待完成，1 = 已完成，2 = 已放弃。"""
    if t.get("dropped"):
        return 2
    return 1 if t.get("done") else 0


class Panel:
    def __init__(self):
        enable_dpi()
        self.pref = {"topmost": False, "w": BASE_W, "h": BASE_H,
                     "x": None, "y": None, "theme": "dark"}
        self.pref.update(load_json(PREFS, {}))
        apply_theme(self.pref.get("theme", "dark"))
        self._last_size = (0, 0)
        self.tab = TABS[0]          # 当前选中的分类，默认「近期任务」
        self._tabs_right = 0
        self._tab_active = None

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.configure(bg=KEY)
        try:
            self.root.attributes("-transparentcolor", KEY)
        except Exception:
            pass
        try:
            self.root.attributes("-alpha", 0.985)
        except Exception:
            pass
        try:
            self.k = max(1.0, self.root.winfo_fpixels("1i") / 96.0)
        except Exception:
            self.k = 1.0

        w = int(self.pref["w"] * self.k) if self.pref["w"] == BASE_W else int(self.pref["w"])
        h = int(self.pref["h"] * self.k) if self.pref["h"] == BASE_H else int(self.pref["h"])
        w = max(w, self.S(MIN_W))
        if self.pref.get("x") is None:
            sw = self.root.winfo_screenwidth()
            x, y = sw - w - self.S(30), self.S(84)
        else:
            x, y = int(self.pref["x"]), int(self.pref["y"])
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.attributes("-topmost", bool(self.pref["topmost"]))

        self.build()
        self.root.mainloop()

    # ---------- 尺寸 / 字体 ----------
    def S(self, n):
        return max(1, int(round(n * self.k)))

    def font(self, size, bold=False, strike=False):
        # 负数 = 像素（正数 = 点，Tk 会再按 DPI 放大一次，导致字号失控）
        px = max(8, int(round(size * 1.3333 * self.k)))
        style = []
        if bold:
            style.append("bold")
        if strike:
            style.append("overstrike")
        return tuple([UI, -px] + style)

    def round_rect(self, cv, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return cv.create_polygon(pts, smooth=True, **kw)

    def card(self, cv, x0, y0, x1, y1, fill):
        """一张圆角卡片 + 底下那层轻微阴影（往右下偏几个像素，做出厚度）。"""
        face = self.round_rect(cv, x0, y0, x1, y1, self.S(R_CARD), fill=fill, outline="")
        sh = self.round_rect(cv, x0 + self.S(2), y0 + self.S(3),
                             x1 + self.S(2), y1 + self.S(3), self.S(R_CARD),
                             fill=SHADOW, outline="")
        # 两次都沉到最底：先把卡面按下去，再把阴影按到卡面之上、也就是全场最底
        cv.tag_lower(face)
        cv.tag_lower(sh)
        return face

    def draw_checkbox(self, cv, x, y, size, filled, done, circle=False):
        """画一个勾选框（含里面的勾），返回 (方框, 勾或 None)，两个都要绑点击。

        勾之前的空框用主色描边，表示「这个可以点」；
        勾上之后就把描边去掉，只剩一个干净的色块（done=已归档，颜色暗一档）。
        circle=True 画成圆的 —— 子条目用它，跟父条目的圆角方框区分开。

        勾是画在方框上面的，点方框中线时会落在勾那条线上；只给方框绑事件的话，
        勾上之后再点方框就没反应了（踩过）。
        """
        face = DONE_BOX if done else ACC
        if filled:
            if circle:
                box = cv.create_oval(x, y, x + size, y + size, fill=face, outline="")
            else:
                box = self.round_rect(cv, x, y, x + size, y + size, self.S(4),
                                      fill=face, outline="")
        else:
            w = max(1, int(round(1.4 * self.k)))
            if circle:
                box = cv.create_oval(x, y, x + size, y + size, fill="",
                                     outline=ACC, width=w)
            else:
                box = self.round_rect(cv, x, y, x + size, y + size, self.S(4),
                                      fill="", outline=ACC, width=w)
        mark = None
        if filled:
            mark = cv.create_line(x + size * 0.26, y + size * 0.52,
                                  x + size * 0.45, y + size * 0.73,
                                  x + size * 0.76, y + size * 0.27,
                                  fill=ON_ACC, width=max(1, int(round(1.9 * self.k))))
        return box, mark

    # ---------- 拖动 / 缩放 ----------
    def drag_start(self, e):
        self._dx, self._dy = e.x, e.y

    def drag_move(self, e):
        self.root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def grip_press(self, e):
        self._resizing = True
        self._rw, self._rh = self.root.winfo_width(), self.root.winfo_height()
        self._rx, self._ry = e.x_root, e.y_root
        self.cv.bind("<B1-Motion>", self.grip_motion)
        self.cv.bind("<ButtonRelease-1>", self.grip_release)

    def grip_motion(self, e):
        if not getattr(self, "_resizing", False):
            return
        w = max(self.S(MIN_W), self._rw + (e.x_root - self._rx))
        h = max(self.S(260), self._rh + (e.y_root - self._ry))
        self.root.geometry(f"{w}x{h}")

    def grip_release(self, e):
        self._resizing = False
        self.cv.unbind("<B1-Motion>")
        self.cv.unbind("<ButtonRelease-1>")

    # ---------- 动作 ----------
    def refresh(self, keep=True):
        # 用「像素偏移」记滚动位置：用比例记会跳，因为勾选后条目会重排
        try:
            off = self.body.canvasy(0)
        except Exception:
            off = 0.0
        try:
            subprocess.run([PY, GEN], cwd=TOOLS, creationflags=0x08000000, timeout=40)
        except Exception:
            pass
        self.render()
        if keep:
            try:
                box = self.body.bbox("all")
                total = max(1.0, float(box[3]) if box else 1.0)
                self.body.yview_moveto(max(0.0, min(1.0, off / total)))
            except Exception:
                pass

    def open_board(self):
        try:
            os.startfile(HTML)
        except Exception:
            pass

    def drop_todo(self, title, on):
        """放弃 / 恢复一条待办。

        状态存在 看板数据.json 的 dropped 里（按标题记），**不写 md** ——
        你的硬约束写明 待办清单.md 只读（除了勾选写回），所以这条只影响小窗。
        后果：md 和 看板.html 里它还是「未完成」的样子。
        """
        d = load_json(DATA, {}) or {}
        names = [str(x) for x in (d.get("dropped") or [])]
        if on:
            if title not in names:
                names.append(title)
        else:
            names = [x for x in names if x != title]
        d["dropped"] = names
        for t in (d.get("todos") or []):
            if t.get("title", "").strip() == title:
                t["dropped"] = on
        save_json(DATA, d)
        self.render()

    def _write_ros(self, st):
        """把 ros_state 写回去，再让生成脚本重算一遍（今日完成、小字进度都在那边算）。"""
        d = load_json(DATA, {}) or {}
        d["ros_state"] = st
        save_json(DATA, d)
        self.refresh()          # refresh 会跑一遍生成脚本，滚动位置照样保留

    def toggle_ros_ep(self, key):
        """勾一集。看完一集算一个小操作 —— 状态存 JSON，不写 md。"""
        if not key:
            return
        d = load_json(DATA, {}) or {}
        st = dict(d.get("ros_state") or {})
        eps = [str(x) for x in (st.get("episodes") or [])]
        eps = [x for x in eps if x != key] if key in eps else eps + [key]
        st["episodes"] = eps
        self._write_ros(st)

    def toggle_ros(self):
        """头那条的勾：一键勾完 / 取消今天那一节的所有集。

        没有逐日安排的时候（退回按周一条），还是老办法：手动切「本周已看完」。
        """
        d = load_json(DATA, {}) or {}
        st = dict(d.get("ros_state") or {})
        eps = [str(x) for x in (st.get("episodes") or [])]
        keys = [t.get("ros_key") for t in (d.get("todos") or [])
                if t.get("kind") == "ros_ep" and t.get("ros_key")]
        if keys:
            on = not all(k in eps for k in keys)
            if on:
                for k in keys:
                    if k not in eps:
                        eps.append(k)
            else:
                drop = set(keys)
                eps = [x for x in eps if x not in drop]
        else:
            st["done"] = not bool(st.get("done"))
        st["episodes"] = eps
        self._write_ros(st)

    def toggle_top(self):
        v = not bool(self.root.attributes("-topmost"))
        self.root.attributes("-topmost", v)
        self.pref["topmost"] = v
        self.draw_footer(self.root.winfo_width(), self.root.winfo_height())

    def toggle_theme(self):
        """按 深色 → 白底 → 橡木 循环，选择存进 小窗口设置.json，下次打开还是这套。"""
        i = THEME_ORDER.index(THEME) if THEME in THEME_ORDER else 0
        apply_theme(THEME_ORDER[(i + 1) % len(THEME_ORDER)])
        self.pref["theme"] = THEME
        save_json(PREFS, self.pref)
        try:
            self.body.configure(bg=WIN)
        except Exception:
            pass
        self.render()

    def set_tab(self, name):
        """切换待办分类：只重画，不动数据。切完回到顶部，免得停在半空。"""
        if name == self.tab:
            return
        self.tab = name
        self.render()
        try:
            self.body.yview_moveto(0.0)
        except Exception:
            pass

    def _tab_hover(self, item, line, hovering):
        """鼠标悬停：未选中的按钮连文字带下划线一起点亮，移开恢复浅灰。"""
        if item == self._tab_active:
            return
        try:
            self.body.itemconfig(item, fill=ACC if hovering else DIM)
            self.body.itemconfig(line, fill=ACC if hovering else TAB_OFF)
        except Exception:
            pass

    def close(self):
        self.pref.update(w=self.root.winfo_width(), h=self.root.winfo_height(),
                         x=self.root.winfo_x(), y=self.root.winfo_y())
        save_json(PREFS, self.pref)
        self.root.destroy()

    def toggle_todo(self, idx):
        d = load_json(DATA, {}) or {}
        todos = d.get("todos") or []
        if idx >= len(todos):
            return
        line = todos[idx].get("line")
        if line is None:
            return
        try:
            with open(TODO_MD, encoding="utf-8") as f:
                lines = f.read().split("\n")
        except Exception:
            return
        if not (0 <= line < len(lines)):
            return
        s = lines[line]
        if "- [ ]" in s:
            lines[line] = s.replace("- [ ]", "- [x]", 1)
        elif "- [x]" in s:
            lines[line] = s.replace("- [x]", "- [ ]", 1)
        elif "- [X]" in s:
            lines[line] = s.replace("- [X]", "- [ ]", 1)
        else:
            return
        try:
            with open(TODO_MD, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception:
            return
        self.refresh()

    def _patch_recurring(self, name, fn):
        """改某个周期任务的进度状态，然后重画。

        状态存在 看板数据.json 的 recurring_state 里，不写 md：
        md 没有「周」的概念，写进去就没法自动重置了。跨周期由 生成看板.py 归零。
        """
        d = load_json(DATA, {}) or {}
        st = dict(d.get(STATE_KEY) or {})
        cur = dict(st.get(name) or {})
        fn(cur)
        st[name] = cur
        d[STATE_KEY] = st
        save_json(DATA, d)
        self.render()

    def toggle_recurring(self, name, undo=False):
        """习惯打卡：一天记一次。

        左键点一下 = 把「今天」加进已完成的日子，本周次数 +1，方框锁住到明天；
        第二天方框自动恢复成可点。右键 = 撤销今天的记录（点错了能退回来）。

        存的是日期列表，不是计数器 —— 参考 punchcard 那类开源习惯追踪器的做法：
        本周几次、跨周归零，全都从日期列表现算，不会出现计数和事实对不上的情况。
        """
        today = date.today().isoformat()

        def fn(cur):
            try:
                days = [str(x) for x in (cur.get("dates") or [])]
            except Exception:
                days = []
            if undo:
                days = [d for d in days if d != today]
            elif today not in days:
                days.append(today)
            cur["dates"] = days[-120:]      # 只留最近的，别无限长
        self._patch_recurring(name, fn)

    # ---------- 骨架 ----------
    def build(self):
        self.cv = tk.Canvas(self.root, bg=KEY, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        self.body = tk.Canvas(self.root, bg=WIN, highlightthickness=0, bd=0)
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.body.bind_all(seq, self.on_wheel)
        self._pending = None
        self.cv.bind("<Configure>", self.on_configure)
        self.render()

    def on_configure(self, e=None):
        """防抖：拖动或缩放时不要每一帧都重绘，否则会卡住。"""
        try:
            if self._pending:
                self.root.after_cancel(self._pending)
        except Exception:
            pass
        self._pending = self.root.after(200, self.render)

    def on_wheel(self, e):
        d = 0
        if getattr(e, "num", None) == 4:
            d = -1
        elif getattr(e, "num", None) == 5:
            d = 1
        elif getattr(e, "delta", 0):
            d = -1 if e.delta > 0 else 1
        if d:
            try:
                self.body.yview_scroll(d * 2, "units")
            except Exception:
                pass

    def render(self):
        W, H = self.root.winfo_width(), self.root.winfo_height()
        if W < 60 or H < 60:
            return
        self.cv.delete("all")
        self.round_rect(self.cv, 0, 0, W, H, self.S(R_WIN), fill=WIN, outline="")
        head_h = self.S(40)
        foot_h = self.S(40)
        self.body.place(x=0, y=head_h, width=W, height=max(10, H - head_h - foot_h))
        self.draw_head(W)
        self.draw_footer(W, H)
        self.draw_body(W)

    # ---------- 顶栏 ----------
    def draw_head(self, W):
        cv = self.cv
        cv.delete("head")
        d = load_json(DATA, {}) or {}
        title = "大学看板"
        week = ""
        if d:
            title = f'{d.get("today", "")[5:]} {d.get("weekday", "")}'
            week = f'第 {d.get("week", "")} 周'
        t = cv.create_text(self.S(16), self.S(20), text=title, anchor="w",
                           font=self.font(12, True), fill=FG, tags=("head", "drag"))
        bb = cv.bbox(t)
        cv.create_text(bb[2] + self.S(10), self.S(21), text=week, anchor="w",
                       font=self.font(8.5), fill=DIM, tags=("head", "drag"))
        x = cv.create_text(W - self.S(18), self.S(20), text="✕", anchor="e",
                           font=self.font(11), fill=DIM, tags=("head", "close"))
        cv.tag_bind("close", "<Button-1>", lambda e: self.close())
        cv.tag_bind("close", "<Enter>", lambda e: cv.itemconfig(x, fill=HOVER))
        cv.tag_bind("close", "<Leave>", lambda e: cv.itemconfig(x, fill=DIM))
        cv.tag_bind("drag", "<Button-1>", self.drag_start)
        cv.tag_bind("drag", "<B1-Motion>", self.drag_move)

    # ---------- 底栏 ----------
    def draw_footer(self, W, H):
        cv = self.cv
        cv.delete("foot")
        y = H - self.S(28)
        items = [("刷新", self.refresh, FG), ("看板", self.open_board, FG),
                 ("已置顶" if self.pref.get("topmost") else "未置顶", self.toggle_top,
                  ACC if self.pref.get("topmost") else DIM),
                 (THEME_LABEL.get(THEME, "深色"), self.toggle_theme, DIM)]
        x = self.S(16)
        for label, cmd, color in items:
            it = cv.create_text(x, y, text=label, anchor="w", font=self.font(9),
                                fill=color, tags="foot")
            bb = cv.bbox(it)
            cv.tag_bind(it, "<Button-1>", lambda e, c=cmd: c())
            cv.tag_bind(it, "<Enter>", lambda e, i=it: cv.itemconfig(i, fill=ACC))
            cv.tag_bind(it, "<Leave>", lambda e, i=it, c=color: cv.itemconfig(i, fill=c))
            x = bb[2] + self.S(16)
        g = cv.create_text(W - self.S(18), y, text="◢", anchor="e",
                           font=self.font(11), fill=FAINT, tags=("foot", "grip"))
        cv.tag_bind("grip", "<Button-1>", self.grip_press)
        cv.tag_bind("grip", "<Enter>", lambda e: cv.itemconfig(g, fill=ACC))
        cv.tag_bind("grip", "<Leave>", lambda e: cv.itemconfig(g, fill=FAINT))

    # ---------- 待办分类按钮 ----------
    def draw_tabs(self, cv, x_start, x_limit, y):
        """三个 Tab 横排在「待办」右边，每个字下面压一条下划线（选中的是蓝的）。

        没有底色块、没有边框：下划线就是唯一的激活标记。文字底下垫了一块和卡片同色的
        隐形区，所以点击不用精准点到字上。间距按可用宽度自动分配，拉窄也不会顶出卡片。
        返回下划线的 y，调用方拿它去画 Tab 下面那条分隔线。
        """
        pad = self.S(3)          # 下划线比文字左右各宽这点（也是点击区留白）
        vpad = self.S(3)         # 文字上下留白
        gap_min, gap_max = self.S(4), self.S(12)
        avail = max(self.S(60), x_limit - x_start)

        def lay(fnt, gap):
            """按给定字号和间距摆三个文字，返回 (每行 [名字, item, bbox], 总占宽)。

            必须用画布 bbox 量，不能用 tkfont.measure —— 后者比实际窄 4~6 像素，
            照它排会顶出卡片（这是踩过的坑）。
            """
            rows, x = [], x_start
            for name in TABS:
                it = cv.create_text(x + pad, y, text=name, anchor="nw", font=fnt,
                                    fill=ACC if name == self.tab else DIM)
                bb = cv.bbox(it)
                rows.append([name, it, bb])
                x = bb[2] + pad + gap
            return rows, rows[-1][2][2] + pad - x_start

        fs = 9
        rows, used = lay(self.font(fs), gap_min)
        for cand in (8, 7):              # 太挤就收一档字号，先量再用
            if used <= avail:
                break
            fs = cand
            for r in rows:
                cv.delete(r[1])
            rows, used = lay(self.font(fs), gap_min)
        slack = max(0, avail - used)
        gap = max(gap_min, min(gap_max, gap_min + slack // max(1, len(TABS) - 1)))
        if gap > gap_min:                # 有富余就重新摊开
            for r in rows:
                cv.delete(r[1])
            rows, used = lay(self.font(fs), gap)

        u_y = y + self.S(18)
        for i, (name, it, bb) in enumerate(rows):
            on = (name == self.tab)
            hit = cv.create_rectangle(bb[0] - pad, bb[1] - vpad, bb[2] + pad, bb[3] + vpad,
                                      fill=CARD2, outline="")
            cv.tag_lower(hit, it)          # 底色块压在文字下面
            u_y = bb[3] + self.S(3)
            line = cv.create_line(bb[0] - pad, u_y, bb[2] + pad, u_y,
                                  fill=ACC if on else TAB_OFF,
                                  width=max(1, int(round((2 if on else 1) * self.k))))
            tag = "tab%d" % i
            cv.itemconfig(it, tags=(tag,))
            cv.itemconfig(hit, tags=(tag,))
            cv.itemconfig(line, tags=(tag,))
            if on:
                self._tab_active = it
            cv.tag_bind(tag, "<Button-1>", lambda e, n=name: self.set_tab(n))
            cv.tag_bind(tag, "<Enter>", lambda e, w=it, l=line: self._tab_hover(w, l, True))
            cv.tag_bind(tag, "<Leave>", lambda e, w=it, l=line: self._tab_hover(w, l, False))
        self._tabs_right = rows[-1][2][2] + pad
        return u_y

    # ---------- 内容 ----------
    def draw_body(self, W):
        cv = self.body
        cv.delete("all")
        d = load_json(DATA, {}) or {}
        y = self.S(6)
        if not d:
            cv.create_text(self.S(16), y + self.S(14), text="点下面的「刷新」生成数据",
                           anchor="nw", font=self.font(9.5), fill=DIM)
            cv.configure(scrollregion=(0, 0, W, y + self.S(50)))
            return
        y = self.draw_schedule(cv, W, y, d)
        y = self.draw_todos(cv, W, y, d)
        cv.configure(scrollregion=(0, 0, W, y + self.S(8)))

    def draw_schedule(self, cv, W, y, d):
        """顶部卡片：最上面一行日期标题横跨整行，下面分左右两栏。

        左栏 = 今日课程 + 明日预览（内容、字号、配色全部沿用原来的，只是宽度收窄）
        右栏 = 本周周期任务（独立管理，不在下方待办列表里重复出现）
        """
        x0, x1 = self.S(10), W - self.S(10)
        px, rx = x0 + self.S(14), x1 - self.S(14)
        top = y

        # 日期标题：横跨整行
        ty = y + self.S(13)
        ds = d.get("today", "")
        head = (f'{ds[5:]} {d.get("weekday", "")} · 第 {d.get("week", "")} 周'
                if ds else "今日日程")
        cv.create_text(px, ty, text=head, anchor="nw", font=self.font(11.5, True), fill=FG)

        # 今晚有没有晚修：放假当天肯定没有；平时只要当天有 19:30 之后才下课的课就算免晚修
        night_class = bool(d.get("today_off")) or any(
            (c.get("end") or "") >= "19:30" for c in (d.get("classes") or []))
        cv.create_text(rx, ty + self.S(1), anchor="ne", font=self.font(11.5, True),
                       text="🎉今天没晚修" if night_class else "😐今天有晚修",
                       fill=GREEN if night_class else ORANGE)

        # 分栏：中间留出垂直分隔线的位置
        col_top = ty + self.S(28)
        gutter = self.S(12)
        usable = max(self.S(120), (rx - px) - 2 * gutter)
        left_x1 = px + int(usable * 0.56)
        mid = left_x1 + gutter
        right_x0 = mid + gutter

        y_left = self.draw_courses(cv, px, left_x1, col_top, d)
        y_right = self.draw_cycles(cv, right_x0, rx, col_top, d)
        bottom = max(y_left, y_right, col_top + self.S(36)) + self.S(12)

        cv.create_line(mid, col_top - self.S(8), mid, bottom - self.S(10), fill=LINE1)
        self.card(cv, x0, top, x1, bottom, CARD1)
        return bottom + self.S(GAP_CARD)

    def draw_courses(self, cv, px, x1, y, d):
        """左栏：今日课程 + 明日预览。"""
        cv.create_text(px, y, text="今日课程", anchor="nw",
                       font=self.font(11.5, True), fill=FG)
        y += self.S(27)
        cl = d.get("classes") or []
        if cl:
            for c in cl:
                # 蓝色标签里写「上课-下课」（下课 = 上课 + 100 分钟）
                ch = self.S(19)
                label = time_range(c)
                tlab = cv.create_text(px + self.S(9), y + ch / 2 + self.S(0.5), text=label,
                                      anchor="w", font=self.font(8.5, True), fill=ON_ACC)
                tb = cv.bbox(tlab)
                chip = self.round_rect(cv, px, y, tb[2] + self.S(9), y + ch,
                                       self.S(5), fill=ACC, outline="")
                cv.tag_lower(chip, tlab)
                cv.create_text(tb[2] + self.S(22), y + ch / 2 + self.S(0.5),
                               text=c["course"], anchor="w",
                               font=self.font(10.5, True), fill=FG)
                y += ch + self.S(8)
        else:
            cv.create_text(px, y, text="今天没课", anchor="nw", font=self.font(9.5), fill=DIM)
            y += self.S(22)
        tm = d.get("tomorrow") or []
        if tm:
            y += self.S(2)
            cv.create_line(px, y, x1, y, fill=LINE1)
            y += self.S(10)
            cv.create_text(px, y, text="明日预览", anchor="nw", font=self.font(8.5), fill=FAINT)
            y += self.S(16)
            for c in tm:
                t1 = cv.create_text(px + self.S(2), y, text=time_range(c), anchor="nw",
                                    font=self.font(8), fill=TINY)
                cv.create_text(cv.bbox(t1)[2] + self.S(8), y, text=c["course"], anchor="nw",
                               font=self.font(9), fill=FAINT)
                y += self.S(17)
            y += self.S(3)
        else:
            y += self.S(14)
        return y

    def draw_cycles(self, cv, x0, x1, y, d):
        """右栏：本周周期任务。只认 kind=recurring 的条目，状态读 recurring_state。

        每条 = 复选框 + 标题 + 本周进度。勾上 = 记一次 +1，取消 = 撤销 -1。
        """
        todos = d.get("todos") or []
        state = d.get(STATE_KEY) or {}
        recs = [(i, t) for i, t in enumerate(todos) if t.get("kind") == "recurring"]

        cv.create_text(x0, y + self.S(1), text="本周周期任务", anchor="nw",
                       font=self.font(10.5, True), fill=FG,
                       width=max(self.S(40), x1 - x0))      # 栏窄了就自动折行，不顶出卡片
        y += self.S(27)
        if not recs:
            cv.create_text(x0, y, text="本周没有周期任务", anchor="nw",
                           font=self.font(9), fill=FAINT)
            return y + self.S(20)

        title_px = max(8, int(round(10 * 1.3333 * self.k)))
        line_h = title_px * 1.5
        box_size = self.S(14)
        today = date.today()
        for idx, t in recs:
            name = t.get("title", "").strip()
            cur = state.get(name) or {}
            target = int(t.get("target") or 0)
            days = cur.get("dates") or []
            count = week_count(days, today)
            marked = done_today(days, today)

            by = y + max(0, (line_h - box_size) / 2)
            box, mark = self.draw_checkbox(cv, x0, by, box_size, marked, False)
            tx = x0 + box_size + self.S(9)
            tit = cv.create_text(tx, y, text=name, anchor="nw",
                                 font=self.font(10, True),
                                 fill=FG,
                                 width=max(self.S(36), x1 - tx))
            y = cv.bbox(tit)[3]
            note = ("本周进度：已完成%d/%d" % (count, target)) if target else t.get("note", "")
            if marked:
                note += " · 今天已完成"
            nt = cv.create_text(tx + self.S(6), y + self.S(2), text=note, anchor="nw",
                                font=self.font(8), fill=TINY,
                                width=max(self.S(36), x1 - tx - self.S(6)))
            y = cv.bbox(nt)[3] + self.S(9)

            if marked:
                # 今天已经打过卡：左键锁住（不响应），右键可以撤销今天的记录
                def undo(e, n=name):
                    self.toggle_recurring(n, undo=True)
                for it in (box, mark, tit):
                    if it is not None:
                        cv.tag_bind(it, "<Button-3>", undo)
            else:
                def handler(event, n=name):
                    self.toggle_recurring(n)
                for it in (box, tit):
                    if it is not None:
                        cv.tag_bind(it, "<Button-1>", handler)
                cv.tag_bind(box, "<Enter>", lambda e, b=box: cv.itemconfig(
                    b, outline=ACC, width=max(1, int(round(2 * self.k)))))
        return y

    def _drop_button(self, cv, x1, y, idx, title, drop):
        """待办行右边那颗「放弃 / 恢复」键。返回它占掉的宽度，好让标题让开。"""
        btn = cv.create_text(x1 - self.S(14), y + self.S(2), text="↩" if drop else "×",
                             anchor="ne", font=self.font(9), fill=DIM)
        bb = cv.bbox(btn)
        hit = cv.create_rectangle(bb[0] - self.S(5), bb[1] - self.S(4),
                                  bb[2] + self.S(4), bb[3] + self.S(4),
                                  fill=CARD2, outline="")
        cv.tag_lower(hit, btn)
        tag = "drop%d" % idx
        cv.itemconfig(btn, tags=(tag,))
        cv.itemconfig(hit, tags=(tag,))
        if drop:
            cv.tag_bind(tag, "<Button-1>", lambda e, n=title: self.drop_todo(n, False))
            cv.tag_bind(tag, "<Enter>", lambda e, w=btn: cv.itemconfig(w, fill=ACC))
        else:
            cv.tag_bind(tag, "<Button-1>", lambda e, n=title: self.drop_todo(n, True))
            cv.tag_bind(tag, "<Enter>", lambda e, w=btn: cv.itemconfig(w, fill=RED))
        cv.tag_bind(tag, "<Leave>", lambda e, w=btn: cv.itemconfig(w, fill=DIM))
        return (x1 - self.S(14) - bb[0]) + self.S(8)

    def draw_todo_item(self, cv, px, x1, y, idx, t, today, box_size, line_h,
                       indent=0, title_size=10, last=True, circle=False):
        """画一条待办，返回画完之后的 y。

        indent > 0 就是子条目（缩进 + 字号小一档 + 圆形勾选框）；
        last=False 会在下面画一条行间细线。
        """
        arch = bool(t.get("done"))
        drop = bool(t.get("dropped"))
        is_ros = (t.get("kind") == "ros")
        is_rep = (t.get("kind") == "ros_ep")
        faded = arch or drop
        filled = arch or bool(t.get("ros_done"))
        title_key = t.get("title", "").strip()
        urgent = False
        due = t.get("due")
        if due and not faded:
            try:
                urgent = 0 <= (date.fromisoformat(due) - today).days <= URGENT_DAYS
            except Exception:
                urgent = False

        bx = px + indent
        by = y + max(0, (line_h - box_size) / 2)
        # 已完成 = 删除线 + 降透明度（Tk 画布没有 alpha，用往卡片底色混色模拟）
        box, mark = self.draw_checkbox(cv, bx, by, box_size, filled, arch, circle=circle)
        if drop and not arch:
            cv.itemconfig(box, outline=FAINT)      # 放弃的框：暗描边，不是亮的
        tx = bx + box_size + self.S(10)

        # 右边那颗「放弃 / 恢复」键。ROS 那几条不给 —— 它们是自动生成的，放弃没意义
        right_pad = 0
        if not (is_ros or is_rep):
            right_pad = self._drop_button(cv, x1, y, idx, title_key, drop)

        tw = max(self.S(80), x1 - self.S(14) - tx - right_pad)
        title = t.get("title", "")
        fill, strike = (DONE_FG, True) if faded else ((ORANGE, False) if urgent else (FG, False))
        tit = cv.create_text(tx, y, text=title, anchor="nw",
                             font=self.font(title_size, True, strike),
                             fill=fill, width=tw)
        y = cv.bbox(tit)[3]

        note = t.get("note", "")
        if drop:
            # 放弃的条目在 md 里还是「未完成」的样子，所以这里明确写出来，
            # 免得跟「已完成」混在一起（之前就是这里让人以为是排序坏了）
            note = ("已放弃 · " + note) if note else "已放弃"
        if note:
            short = note if len(note) <= 58 else note[:57] + "…"
            nt = cv.create_text(tx + self.S(7), y + self.S(2), text=short, anchor="nw",
                                font=self.font(8), fill=TINY, width=tw - self.S(7))
            y = cv.bbox(nt)[3]
        y += self.S(9)
        if not last:
            cv.create_line(tx, y - self.S(4), x1 - self.S(14), y - self.S(4), fill=LINE2)

        if is_rep:
            # ROS 的某一集：勾它就完事，只动 JSON，不写 md
            def handler(event, k=t.get("ros_key")):
                self.toggle_ros_ep(k)
        elif is_ros:
            # ROS 头那条：一键勾完 / 取消今天这一节的全部集
            def handler(event):
                self.toggle_ros()
        else:
            def handler(event, k=idx):
                self.toggle_todo(k)
        for it in (box, mark):
            if it is not None:
                cv.tag_bind(it, "<Button-1>", handler)
        cv.tag_bind(tit, "<Button-1>", handler)
        if not faded:
            # 只有正常状态的框才做悬停加粗 —— 勾上/放弃的框不要蓝色描边
            cv.tag_bind(box, "<Enter>", lambda e, b=box: cv.itemconfig(
                b, outline=ACC, width=max(1, int(round(2 * self.k)))))
        return y

    def draw_todos(self, cv, W, y, d):
        x0, x1 = self.S(10), W - self.S(10)
        px = x0 + self.S(14)
        top = y
        y += self.S(13)
        todos = d.get("todos") or []

        # 只挑出当前分类的条目；下标是 md 里的原始行号，写回全靠它，必须原样带着走。
        # 周期任务已经搬到顶部卡片的右栏，这里不再重复出现。
        pairs = [(i, t) for i, t in enumerate(todos)
                 if tab_of(t.get("section", "")) == self.tab
                 and t.get("kind") != "recurring"
                 and not t.get("aged")]
        n_aged = len([t for t in todos
                      if tab_of(t.get("section", "")) == self.tab
                      and t.get("kind") != "recurring" and t.get("aged")])
        n_done = len([t for _, t in pairs if t.get("done")])
        n_drop = len([t for _, t in pairs if t.get("dropped") and not t.get("done")])
        n_open = len(pairs) - n_done - n_drop      # 放弃的不算「待办」

        self._tab_active = None
        t_title = cv.create_text(px, y, text="待办", anchor="nw",
                                 font=self.font(13.5, True), fill=FG)
        uy = self.draw_tabs(cv, cv.bbox(t_title)[2] + self.S(12), x1 - self.S(14),
                            y + self.S(4))
        cnt = cv.create_text(x1 - self.S(14), y + self.S(3),
                             text=f"{n_open} 待办 · {n_done} 已完成",
                             anchor="ne", font=self.font(8.5), fill=FAINT)
        if cv.bbox(cnt)[0] < self._tabs_right + self.S(10):
            cv.delete(cnt)          # 窗口太窄就让位，不跟 Tab 挤在一起
        # Tab 下面那条通长分隔线
        dy = uy + self.S(6)
        cv.create_line(px, dy, x1 - self.S(14), dy, fill=LINE2)
        y = dy + self.S(11)

        today = date.today()
        title_px = max(8, int(round(10 * 1.3333 * self.k)))
        line_h = title_px * 1.5
        box_size = self.S(14)

        # ROS 那一组（头 + 今天每一集）单独画在最前面，作为一个整体：
        #   ① 子条目缩进 + 一条竖线，从属关系一眼看得出来
        #   ② 勾掉一集它不会被挪到下面的「已完成」块去，跟父条目拆散
        ros_rows = [(i, t) for i, t in pairs if str(t.get("kind", "")).startswith("ros")]
        pairs = [(i, t) for i, t in pairs if not str(t.get("kind", "")).startswith("ros")]
        if ros_rows:
            y += self.S(2)
            g_top = None
            for i, (idx, t) in enumerate(ros_rows):
                child = (t.get("kind") == "ros_ep")
                if child and g_top is None:
                    g_top = y - self.S(2)
                y = self.draw_todo_item(cv, px, x1, y, idx, t, today, box_size, line_h,
                                        indent=self.S(16) if child else 0,
                                        title_size=9 if child else 10, circle=child,
                                        last=(i == len(ros_rows) - 1))
            if g_top is not None:
                # 竖线画在头那条方框的正下方，一直拉到最后一集，像树枝
                cv.create_line(px + self.S(7), g_top, px + self.S(7), y - self.S(9),
                               fill=LINE2)

        # 剩下的按状态分三块：待完成 / 已完成 / 已放弃，各挂一个小标签。
        # 以前是「先按 md 的分组、组内再按状态」，结果下一组的未完成条目会排到
        # 上一组的已完成下面 —— 看着就像"错位"。
        first_block = not ros_rows
        for rk, label in ((0, "待完成"), (1, "已完成"), (2, "已放弃")):
            group = [(i, t) for i, t in pairs if todo_rank(t) == rk]
            if not group:
                continue
            y += self.S(2) if first_block else self.S(8)
            if not first_block:
                cv.create_line(px, y, x1 - self.S(14), y, fill=LINE2)
                y += self.S(6)
            cv.create_text(px, y, text=label, anchor="nw",
                           font=self.font(8.5, True), fill=FAINT)
            y += self.S(18)
            first_block = False
            for i, (idx, t) in enumerate(group):
                y = self.draw_todo_item(cv, px, x1, y, idx, t, today, box_size, line_h,
                                        last=(i == len(group) - 1))

        # 被收起来的那些，在卡片底部留一句，免得以为它们凭空消失了
        if n_aged:
            y += self.S(4)
            cv.create_line(px, y, x1 - self.S(14), y, fill=LINE2)
            y += self.S(7)
            at = cv.create_text(px, y, text="已收起 %d 条（完成 / 放弃超过半个月）" % n_aged,
                                anchor="nw", font=self.font(8), fill=FAINT)
            y = cv.bbox(at)[3]
        y = max(y, top + self.S(44))
        self.card(cv, x0, top, x1, y, CARD2)
        return y + self.S(GAP_CARD)


if __name__ == "__main__":
    Panel()
