# -*- coding: utf-8 -*-
"""生成看板：读取「本脚本所在目录的上一级」下的 md，产出 看板.html 和 看板数据.json。

用法：把本文件和 小窗口.py 一起放进工作区的 _工具 目录，然后 python 生成看板.py
不用装任何第三方库。

看板数据.json 里除了生成物，还额外承担一件小事：周期任务的进度计数，
放在 recurring_state 里。生成时会把上一份文件里的进度原样带过来，
只有跨过周期边界（比如进入新的一周）才归零。所以别手删这个文件，
删了等于把「本周跑了第几次」清零。
"""

import os
import re
import sys
import json
import html as H
from datetime import date, datetime, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ╔══════════════════════════════════════════════════════════════════╗
# ║  配置区：装看板时只改这一段，下面的代码不要动                       ║
# ╚══════════════════════════════════════════════════════════════════╝

# ① 工作区根目录。默认 = 本脚本所在目录的上一级（脚本放在 <工作区>\_工具\ 下），
#    所以工作区搬到别处也不用改。
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_HTML = os.path.join(ROOT, "看板.html")
OUT_JSON = os.path.join(ROOT, "_工具", "看板数据.json")

# ② 教学周基准：挑一个你**确定**的「某周周一」，填上那天是第几周。
#    ⚠️ 填错的话，看板上的「今天是第几周 / 今天上什么课」会全错。
#    例：2026-09-14 是周一，那天开始第 3 周，就写下面两行。
WEEK3_MONDAY = date(2026, 9, 14)
WEEK3_NUMBER = 3

# ③ 要收录进看板的文档：(相对路径, 显示名, 分组)
#    留空 [] = 自动收录工作区里所有 .md（按顶层文件夹分组，根目录的归到「看板」组）——
#    装完先这样跑，能看之后想收窄再手动写。
#    手动写的时候注意：路径不存在**不报错**，只是那条不出现在看板里。
DOCS = [
    # ("待办清单.md", "待办清单", "看板"),
    # ("档案袋\\课表.md", "课表", "看板"),
]


def auto_docs():
    """DOCS 留空时用：把工作区里的 .md 全收进来。跳过 _工具/ 和隐藏目录。"""
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "_工具"]
        for fn in sorted(filenames):
            if not fn.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
            group = "看板" if os.sep not in rel else rel.split(os.sep)[0]
            out.append((rel, os.path.splitext(fn)[0], group))
    return out


if not DOCS:
    DOCS = auto_docs()


def resolve_doc(rel, basename):
    """给定路径不存在时，在整个工作区里按文件名找一份（同名取最靠前的那个）。"""
    if rel and os.path.exists(os.path.join(ROOT, rel)):
        return rel
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "_工具"]
        for fn in sorted(filenames):
            if fn == basename:
                return os.path.relpath(os.path.join(dirpath, fn), ROOT)
    return rel


SLOT_TIME = {
    "1-2": "07:40", "3-4": "09:45", "5-6": "14:30", "7-8": "16:35", "9-11": "19:20",
}
CLASS_MINUTES = 100      # 每节课（一个时间段）按 100 分钟算，下课时间由上课时间推出来
DOW_CN = ["一", "二", "三", "四", "五", "六", "日"]

# ④ 周期任务（可选，不需要就写 RECURRING = {}）。标题要**正好**等于左边的名字才会被认出来。
#   cycle=week  → 进度按自然周算（ISO 周，周一是新一周的第一天），跨周自然归零
#   target=3    → 本周期要做满 3 次，小窗口显示「本周进度：已完成 n/3」
#   rule        → 周期规则，只作参数和记录，不占条目里的一行
# 例： {"阳光跑": {"cycle": "week", "target": 3, "rule": "每周3次，每次3km"}}
RECURRING = {}

STATE_KEY = "recurring_state"
DROPPED_KEY = "dropped"      # 已放弃的待办：按标题记，存在 看板数据.json 里

# ⑤ 长任务日程（可选，指不到就自动跳过、不报错）。
#    指向一份「按周推进的长任务」md，脚本只读它，自己算出「今天到第几周了」，
#    不用人每周手动改待办。格式见 skill 的 references/kanban.md。
ROS_DOC = "路径/到/你的长任务日程.md"
ROS_KEY = "ros"
ROS_STATE_KEY = "ros_state"      # 「这一周看完了没」，跟习惯打卡一样存在 JSON 里

# ⑦ 课表数据源。路径不对也不要紧 —— 下面主流程会用 resolve_doc 在工作区里按文件名自动找一份 课表.md。
SCHED_DOC = "大学生电子档案袋\\01_学业与成绩\\课表.md"

# 已完成 / 已放弃的条目在看板上留多久（天）。到期就从列表里收起来 ——
# md 里一个字节都不动，只是不再往小窗里画。
AGED_KEY = "aged"                # {标题: {"k": "done"/"dropped", "since": "YYYY-MM-DD"}}
AGED_DAYS = 15

# ---------- 例外日期表 ----------
# 节假日 / 调休：法定节假日那天的课一律不算。这张表优先级最高，覆盖按周次算出来的结果。
#
# 优先从 课表.md 的「## 例外日期」表里读（那样你自己加一行就行，不用改代码）；
# md 里没写就退回下面这份内置的。md 里写了就以 md 为准。
#   | 2026-09-25 | 停课 | 中秋假期 |        ← 这天全部停课
#   | 2026-10-10 | 补课 | 按周三上 |        ← 这天按周三的课表上（调休补课）
# ⑥ 内置兜底（可以留空）。平时不用改这里 ——
#    直接在 课表.md 的「## 例外日期」表里加一行更省事，md 优先。
#    {"2027-01-01": {"stop": True, "note": "元旦"},
#     "2026-10-10": {"as": 3, "note": "调休补课，按周三上"}}    ← as: 0=周一 … 6=周日
BUILTIN_EXCEPTIONS = {}

WEEK_CN = "一二三四五六日"

# ══════════════════ 配置区结束（下面都是代码，不用改）══════════════════


# ---------- markdown -> html ----------

def inline(s):
    s = H.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![=\"'/(])(https?://[^\s<>()，。]+)", r'<a href="\1" target="_blank">\1</a>', s)
    return s


def md_to_html(md):
    lines = md.split("\n")
    out, i, n = [], 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if s.startswith("```"):
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + H.escape("\n".join(buf)) + "</code></pre>")
            continue
        if s.startswith("|") and i + 1 < n and re.match(r"^\|[\s:|\-]+\|$", lines[i + 1].strip()):
            head = [c.strip() for c in s.strip("|").split("|")]
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            t = ["<table><thead><tr>"]
            t += ["<th>" + inline(h) + "</th>" for h in head]
            t.append("</tr></thead><tbody>")
            for r in rows:
                t.append("<tr>" + "".join("<td>" + inline(c) + "</td>" for c in r) + "</tr>")
            t.append("</tbody></table>")
            out.append("".join(t))
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            lv = len(m.group(1))
            out.append(f"<h{lv}>{inline(m.group(2))}</h{lv}>")
            i += 1
            continue
        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote>" + "<br>".join(inline(b) for b in buf if b) + "</blockquote>")
            continue
        if re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
            items = []
            while i < n and re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                raw = lines[i]
                indent = len(raw) - len(raw.lstrip())
                txt = re.sub(r"^\s*([-*]|\d+\.)\s+", "", raw).strip()
                cb = ""
                mm = re.match(r"^\[( |x|X)\]\s*(.*)$", txt)
                if mm:
                    chk = " checked" if mm.group(1).lower() == "x" else ""
                    cb = f'<input type="checkbox" disabled{chk}> '
                    txt = mm.group(2)
                cls = ' class="sub"' if indent >= 2 else ""
                items.append(f"<li{cls}>{cb}{inline(txt)}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        if not s:
            i += 1
            continue
        buf = [s]
        i += 1
        while i < n and lines[i].strip() and not re.match(r"^(#|>|\||[-*]\s|\d+\.\s|```)", lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>" + "<br>".join(inline(b) for b in buf) + "</p>")
    return "\n".join(out)


# ---------- 数据解析 ----------

def read(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return f.read()


def parse_weeks(s):
    s = re.sub(r"[（(].*?[)）]", "", s).replace("周", "").strip()
    if not s:
        return None
    out = []
    for part in re.split(r"[,，、]", s):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(\d+)\s*-\s*(\d+)$", part)
        if m:
            out.extend(range(int(m.group(1)), int(m.group(2)) + 1))
            continue
        m = re.match(r"^(\d+)$", part)
        if m:
            out.append(int(m.group(1)))
            continue
        return None
    return out or None


def parse_schedule(md):
    """从课表.md 的「各时段的周次」表解析。"""
    rows = []
    for m in re.finditer(r"^\|\s*([^|]+?)\s*\|\s*周([一二三四五六日])\s+([\d\-]+)\s*节\s*\|\s*([^|]+?)\s*\|\s*$", md, re.M):
        course = m.group(1).strip()
        dow = "一二三四五六日".index(m.group(2))
        slot = m.group(3).strip()
        weeks = parse_weeks(m.group(4))
        if weeks is None or course.startswith("课程") or course.startswith("---"):
            continue
        rows.append({"course": course, "dow": dow, "slot": slot, "weeks": weeks})
    return rows


def parse_ros_weeks(md):
    """解析 ROS教程学习日程.md 里的 8 周表。

    表长这样（第一格是周次数字，一共 7 列）：
      | **1** | 10/08（四）—10/11（日） | 4 | 001—015 | 17 | 2h10m | ~32 分 |
    只认第一格是纯数字的行，所以不会误吃文件里别的表格。
    """
    out = []
    ym = re.search(r"（(\d{4})-", md)
    year = int(ym.group(1)) if ym else date.today().year
    for m in re.finditer(r"^\|\s*\*{0,2}(\d+)\*{0,2}\s*\|(.+)\|\s*$", md, re.M):
        cells = [c.replace("*", "").strip() for c in m.group(2).split("|")]
        if len(cells) != 6:
            continue
        ds = re.findall(r"(\d{1,2})/(\d{1,2})", cells[0])
        if len(ds) < 2:
            continue
        try:
            start = date(year, int(ds[0][0]), int(ds[0][1]))
            end = date(year, int(ds[-1][0]), int(ds[-1][1]))
        except Exception:
            continue
        out.append({"n": int(m.group(1)), "start": start, "end": end,
                    "days": cells[1], "what": cells[2],
                    "eps": cells[3], "dur": cells[4], "perday": cells[5]})
    return out


def parse_ros_days(md):
    """解析「## 逐日安排」：按 ### YYYY-MM-DD 切小节，小节下的 - <编号> 一集一条。

    这一节由 ROS 学习子会话维护、每天往后追加，所以只读到下一个二级标题为止。
    编号 2026-10-09 起改用「B站标题号」（如 `022`），同时兼容老的 `P24` 写法
    —— 标题号 = 分P号 − 2（分P ≤ 14 同号，分P 15/16 是 `014补充1/2`）。
    ep 原样进 ros_key（如 `2026-10-09|022`），所以改口径会让旧勾选对不上号。
    返回 {日期: {"label":…, "goal":…, "items":[{"ep":"022","text":"…"}]}}
    """
    out = {}
    head = re.search(r"^##\s*逐日安排[^\n]*$", md, re.M)
    if not head:
        return out
    body = md[head.end():]
    nxt = re.search(r"^##\s+\S", body, re.M)
    if nxt:
        body = body[:nxt.start()]
    cur = None
    for raw in body.split("\n"):
        s = raw.strip()
        h = re.match(r"^###\s*(\d{4})-(\d{2})-(\d{2})\s*(.*)$", s)
        if h:
            ds = "%s-%s-%s" % (h.group(1), h.group(2), h.group(3))
            rest = h.group(4).strip()
            gm = re.search(r"目标\s*([0-9]+\s*分钟)", rest)
            cur = {"date": ds, "label": rest,
                   "goal": gm.group(1) if gm else "", "items": []}
            out[ds] = cur
            continue
        it = re.match(r"^-\s*(?:\[[ xX]\]\s*)?(P?\d{1,3}(?:补充\d)?)\s*(.*)$", s)
        if it and cur is not None:
            cur["items"].append({"ep": it.group(1), "text": it.group(2).strip()})
    return out


def ros_position(weeks, today):
    """今天落在第几周。返回 (当前周 dict 或 None, 是否还没开始, 是否已结束)。"""
    if not weeks:
        return None, False, False
    for w in weeks:
        if w["start"] <= today <= w["end"]:
            return w, False, False
    if today < weeks[0]["start"]:
        return None, True, False
    return None, False, True


def parse_exceptions(md):
    """从 课表.md 的「## 例外日期」表里读例外日。

    只认第一格是 2026-09-25 这种完整日期的行，所以不会误吃别的表格。
      | 2026-09-25 | 停课 | 中秋假期 |     → 这天全部停课
      | 2026-10-10 | 补课 | 按周三上 |     → 这天按周三的课表上
    返回 {日期: {"stop": True}} 或 {日期: {"as": 星期序号}}，读不到就返回空。
    """
    out = {}
    pat = r"^\|\s*(\d{4})-(\d{2})-(\d{2})\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*$"
    for m in re.finditer(pat, md, re.M):
        ds = "%s-%s-%s" % (m.group(1), m.group(2), m.group(3))
        kind = m.group(4).strip()
        note = m.group(5).strip()
        if kind.startswith(("停", "放", "休")):
            out[ds] = {"stop": True, "note": note}
        elif kind.startswith("补"):
            w = re.search(r"[周星期]\s*([一二三四五六日])", note)
            if w:
                out[ds] = {"as": WEEK_CN.index(w.group(1)), "note": note}
    return out


def build_exceptions(md):
    """md 里那张表优先，没写到的用内置的兜底。"""
    ex = dict(BUILTIN_EXCEPTIONS)
    ex.update(parse_exceptions(md))
    return ex


def parse_todos(md):
    items, section = [], ""
    for idx, ln in enumerate(md.split("\n")):
        s = ln.strip()
        m = re.match(r"^#{2,4}\s+(.*)$", s)
        if m:
            section = m.group(1).strip()
            continue
        m = re.match(r"^-\s*\[( |x|X)\]\s*(.*)$", s)
        if not m:
            continue
        raw = m.group(2).strip()
        title, note = split_todo(raw)
        rec = RECURRING.get(title.strip())
        item = {
            "done": m.group(1).lower() == "x",
            "title": title,
            "note": note,
            "text": title + (" —— " + note if note else ""),
            "section": section,
            "line": idx,
            "due": find_due(title, note),
            "kind": "recurring" if rec else "once",
        }
        if rec:
            item["cycle"] = rec["cycle"]
            item["target"] = rec["target"]
            item["rule"] = rec["rule"]
        items.append(item)
    return items


def split_todo(s):
    """把一条待办拆成「标题 + 备注」。标准写法：**标题** —— 备注"""
    m = re.match(r"^\*\*(.+?)\*\*\s*(.*)$", s, re.S)
    if m:
        title, rest = m.group(1).strip(), m.group(2).strip()
    else:
        parts = re.split(r"\s*[—–]{1,2}\s*", s, maxsplit=1)
        title, rest = parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")
    rest = re.sub(r"^[—–\-:：\s]+", "", rest)
    clean = lambda t: t.replace("**", "").replace("`", "").strip()
    return clean(title), clean(rest)


def _mkdate(mo, dy):
    this_year = date.today().year
    try:
        d = date(this_year, mo, dy)
    except Exception:
        return None
    if (d - date.today()).days < -60:
        try:
            d = date(this_year + 1, mo, dy)
        except Exception:
            return None
    return d.isoformat()


def find_due(title, note):
    """判断这条待办的「截止日」。

    规则（避免把「9/21 已开跑」这种误判成截止日）：
      1. 标题里出现日期 → 算（标题里的日期通常是「这天要做」）
      2. 备注里出现「X 前」或「截止 X」 → 算
      3. 其余不算
    """
    for m in _iter_dates(title):
        v = _mkdate(int(m.group(1)), int(m.group(2)))
        if v:
            return v
    for m in re.finditer(r"(\d{1,2})\s*[/月\-]\s*(\d{1,2})(?:日)?[^0-9\n]{0,8}前", note):
        v = _mkdate(int(m.group(1)), int(m.group(2)))
        if v:
            return v
    for m in re.finditer(r"截止[^0-9]{0,4}(\d{1,2})\s*[/月\-]\s*(\d{1,2})", note):
        v = _mkdate(int(m.group(1)), int(m.group(2)))
        if v:
            return v
    return None


def _iter_dates(text):
    """迭代文本里的日期候选。

    跳过「9-11 节」「第 1-19 周」「跑 60-70 公里」这类区间写法 ——
    它们长得像 月-日，但后面跟的是单位，不是日期。以前只挡了「节」，
    结果「第 1-19 周」被当成 1 月 19 日挂了个假截止日（踩过）。
    """
    for m in re.finditer(r"(\d{1,2})\s*[/月\-]\s*(\d{1,2})", text):
        if re.match(r"\s*(节|周|天|次|公里|km|KM|千米|分钟|分|页|人|个|点)",
                    text[m.end():m.end() + 4]):
            continue
        yield m


def current_week(today):
    return WEEK3_NUMBER + (today - WEEK3_MONDAY).days // 7


def slot_end(hhmm):
    """上课时间 + 100 分钟 = 下课时间。"""
    try:
        h, m = hhmm.split(":")
        base = datetime(2000, 1, 1, int(h), int(m)) + timedelta(minutes=CLASS_MINUTES)
        return base.strftime("%H:%M")
    except Exception:
        return hhmm


def load_prev():
    """把上一份 看板数据.json 整个读回来（没有就给个空壳）。

    这份文件同时兼着「小窗自己的状态」：周期任务的打卡日期、已放弃的待办。
    生成时必须先读回来再合并，不能直接覆盖，否则一按刷新状态就没了。
    """
    try:
        with open(OUT_JSON, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def classes_on(rows, d, exceptions=None):
    """这天有什么课。例外表（法定节假日 / 调休补课）优先级最高。"""
    ex = (exceptions if exceptions is not None else BUILTIN_EXCEPTIONS).get(d.isoformat()) or {}
    if ex.get("stop"):
        return []                      # 法定节假日：课表上排了也不上
    wk = current_week(d)
    dow = ex.get("as")
    dow = int(dow) if dow is not None else d.weekday()
    got = []
    for r in rows:
        if r["dow"] == dow and wk in r["weeks"]:
            start = SLOT_TIME.get(r["slot"], r["slot"])
            got.append({"time": start, "end": slot_end(start),
                        "slot": r["slot"], "course": r["course"]})
    got.sort(key=lambda x: x["time"])
    return got


def main():
    today = date.today()
    data = {"generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "today": today.isoformat(),
            "weekday": "周" + DOW_CN[today.weekday()],
            "week": current_week(today)}

    sched_md = read(resolve_doc(SCHED_DOC, "课表.md")) or ""
    rows = parse_schedule(sched_md)
    exceptions = build_exceptions(sched_md)
    data["classes"] = classes_on(rows, today, exceptions)
    data["tomorrow"] = classes_on(rows, today + timedelta(days=1), exceptions)
    # 今天是不是法定节假日停课（放假当天没有晚自习，小窗要区别对待）
    data["today_off"] = bool((exceptions.get(today.isoformat()) or {}).get("stop"))

    todo_md = read("待办清单.md") or ""
    todos = parse_todos(todo_md)
    prev_json = load_prev()

    # ROS 教程：从日程表里算出「今天是第几周 / 这周看哪些 / 离汇报还有几天」，
    # 合成一条置顶的信息行。**不需要谁每周手动改待办** —— 日期一变它自己就换。
    ros_md = read(ROS_DOC) or ""
    ros_weeks = parse_ros_weeks(ros_md)
    ros_days = parse_ros_days(ros_md)
    cur, not_started, finished = ros_position(ros_weeks, today)
    today_day = ros_days.get(today.isoformat()) or {}
    day_items = today_day.get("items") or []
    n_eps = len(day_items)

    prev_ros = prev_json.get(ROS_STATE_KEY) or {}
    eps_done = [str(x) for x in (prev_ros.get("episodes") or [])]
    cutoff = (today - timedelta(days=60)).isoformat()      # 只留最近两个月的勾
    eps_done = [k for k in eps_done if k[:10] >= cutoff]
    eps_set = set(eps_done)
    day_keys = ["%s|%s" % (today.isoformat(), it["ep"]) for it in day_items]
    n_eps_done = len([k for k in day_keys if k in eps_set])
    wk_n = cur["n"] if cur else (0 if not_started else len(ros_weeks))
    # 有逐日安排就以「今天那一节全勾完」为准；没有就退回老的手动「本周已看完」
    if n_eps:
        ros_done = n_eps_done == n_eps
    else:
        ros_done = bool(prev_ros.get("done")) and prev_ros.get("week") == wk_n

    if ros_weeks:
        last = ros_weeks[-1]
        data[ROS_KEY] = {
            "week": wk_n, "weeks": len(ros_weeks),
            "deadline": last["end"].isoformat(),
            "days_left": (last["end"] - today).days,
            "done": ros_done, "not_started": not_started, "finished": finished,
            "today_eps": n_eps, "today_done": n_eps_done,
        }
        data[ROS_STATE_KEY] = {"week": wk_n, "done": ros_done, "episodes": eps_done}
        data["ros_days"] = ros_days
        if cur:
            data[ROS_KEY].update({"start": cur["start"].isoformat(),
                                  "end": cur["end"].isoformat(),
                                  "what": cur["what"], "eps": cur["eps"],
                                  "dur": cur["dur"], "perday": cur["perday"]})
            fmt = lambda x: "%d/%02d" % (x.month, x.day)
            left = last["end"] - today
            perday = cur["perday"].lstrip("~").strip()      # 表里写的是「~32 分」
            if n_eps:
                note = "今天 %d/%d 集 · 本周 %s · 每天约 %s · 距汇报 %d 天" % (
                    n_eps_done, n_eps, cur["what"], perday, max(0, left.days))
            else:
                note = "%s · %s 集 · %s · 每天约 %s · 距汇报 %d 天" % (
                    cur["what"], cur["eps"], cur["dur"], perday, max(0, left.days))
            if ros_done:
                note += " · 今日完成" if n_eps else " · 本周已看完"
            ros_title = "ROS 第 %d 周 / 共 %d 周（%s—%s）" % (
                cur["n"], len(ros_weeks), fmt(cur["start"]), fmt(cur["end"]))
            ros_rows = [{
                "done": bool(ros_done), "title": ros_title, "note": note,
                "text": ros_title + (" —— " + note if note else ""),
                # 给它自己一个分组名：插在列表最前面，但**不会打乱 md 里其他分组的先后**
                # （之前挂到「有时效的，先做」下面，结果那个分组被顶到最前，
                #  把「这几天」那一组挤到一堆已完成条目的下面 —— 视觉上就是"错位"）
                "section": "ROS 教程", "line": None,
                "due": None, "kind": "ros", "ros_done": ros_done,
                "dropped": False,
            }]
            # 今天这一节的每一集，展开成可单独勾的小条目
            for it in day_items:
                k = "%s|%s" % (today.isoformat(), it["ep"])
                ttl = "%s %s" % (it["ep"], it["text"]) if it["text"] else it["ep"]
                ros_rows.append({
                    "done": k in eps_set, "title": ttl, "note": "",
                    "text": ttl, "section": "ROS 教程", "line": None,
                    "due": None, "kind": "ros_ep", "ros_key": k, "dropped": False,
                })
            todos[0:0] = ros_rows

    data["todos"] = todos                       # 全部（含已完成），面板自己排序
    data["todos_open"] = [t for t in todos if not t["done"]]
    data["todo_done"] = [t for t in todos if t["done"]]

    # 已放弃的待办：按标题记。md 里改了标题就自动失效 —— 宁可让它恢复显示，
    # 也不能认错人把别的条目藏起来。
    titles = set(t["title"].strip() for t in todos)
    dropped = [str(k) for k in (prev_json.get(DROPPED_KEY) or []) if str(k) in titles]
    data[DROPPED_KEY] = dropped
    dropped_set = set(dropped)
    for t in todos:
        t["dropped"] = t["title"].strip() in dropped_set

    # 已完成 / 已放弃的条目：满 15 天就从看板上收起来，免得底下越堆越长。
    # 计时从「第一次看到它是这个状态」那天开始 —— md 里没有完成日期，我不编。
    # 中途改回未完成（取消勾选 / 点↩恢复），计时就作废，重新算。
    prev_aged = prev_json.get(AGED_KEY) or {}
    today_s = today.isoformat()
    aged, aged_out = {}, []
    for t in todos:
        if str(t.get("kind", "")).startswith("ros"):
            continue                      # ROS 那几条是自动生成的，不参与归档计时
        key = t["title"].strip()
        st = "dropped" if t.get("dropped") else ("done" if t.get("done") else "")
        if not st:
            continue
        old = prev_aged.get(key) or {}
        since = str(old.get("since") or "") if old.get("k") == st else ""
        if not since:
            since = today_s
        try:
            days = (today - date.fromisoformat(since)).days
        except Exception:
            days = 0
            since = today_s
        aged[key] = {"k": st, "since": since}
        if days >= AGED_DAYS:
            aged_out.append(key)
            t["aged"] = True
    data[AGED_KEY] = aged
    data["aged_out"] = aged_out

    # 习惯打卡的进度：存的是「已完成的日子」列表，不是计数器（参考 punchcard 那类
    # 开源习惯追踪器的做法）。本周几次、跨周归零，全都从日期列表现算，不会对不上。
    prev = prev_json.get(STATE_KEY) or {}
    state = {}
    for t in todos:
        if t.get("kind") != "recurring":
            continue
        key = t["title"].strip()
        days = (prev.get(key) or {}).get("dates")
        keep = []
        if isinstance(days, list):          # 旧格式（count/finished）没法还原成日期，从空开始
            for ds in days:
                try:
                    if (today - date.fromisoformat(str(ds))).days <= 90:
                        keep.append(str(ds))
                except Exception:
                    pass
        state[key] = {"dates": keep}
    data[STATE_KEY] = state

    # 生成 html 片段
    pages = []
    missing = []
    for rel, name, group in DOCS:
        md = read(rel)
        if md is None:
            missing.append((rel, name))
        body = md_to_html(md) if md else "<p><em>（文件不存在）</em></p>"
        pages.append({"id": re.sub(r"\W+", "-", rel), "name": name, "group": group, "html": body})

    # 今日总览页
    cl = data["classes"]
    if cl:
        cl_html = "".join(f'<li><b>{c["time"]}–{c["end"]}</b> {c["course"]}</li>' for c in cl)
    else:
        cl_html = "<li>今天没课</li>"
    tm = data["tomorrow"]
    tm_html = "".join(f'<li><b>{c["time"]}–{c["end"]}</b> {c["course"]}</li>' for c in tm) or "<li>明天没课</li>"
    td = data["todos_open"][:12]
    td_html = "".join(f'<li>{inline(t["text"])} <span class="sec">{t["section"]}</span></li>' for t in td) or "<li>没有待办</li>"
    overview = (
        f'<h1>{today.isoformat()} {data["weekday"]} · 第 {data["week"]} 教学周</h1>'
        f"<h2>今天的课</h2><ul>{cl_html}</ul>"
        f"<h2>明天</h2><ul>{tm_html}</ul>"
        f"<h2>待办（前 12 条）</h2><ul>{td_html}</ul>"
        f'<p class="sec">生成时间：{data["generated"]}</p>'
    )
    pages.insert(0, {"id": "today", "name": "今日总览", "group": "看板", "html": overview})

    # 导航
    groups = {}
    for p in pages:
        groups.setdefault(p["group"], []).append(p)
    nav = []
    order = ["看板", "学业", "职务", "生活", "档案"]
    for g in order + [k for k in groups if k not in order]:
        if g not in groups:
            continue
        nav.append(f'<div class="grp">{g}</div>')
        for p in groups[g]:
            nav.append(f'<div class="item" data-id="{p["id"]}">{H.escape(p["name"])}</div>')

    page_html = "".join(f'<section id="{p["id"]}" class="page">{p["html"]}</section>' for p in pages)

    doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>大学看板</title>
<style>
:root{{--bg:#f7f7f5;--fg:#1c1c1e;--dim:#6b6b70;--line:#e2e2df;--card:#fff;--acc:#0a6cff}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16161a;--fg:#e8e8ea;--dim:#9a9aa0;--line:#2b2b31;--card:#1e1e24;--acc:#5aa2ff}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15.5px/1.75 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}}
header{{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 18px;display:flex;align-items:baseline;gap:14px;z-index:5}}
header b{{font-size:17px}}
header span{{color:var(--dim);font-size:13px}}
.wrap{{display:flex;gap:0;align-items:flex-start}}
nav{{width:210px;flex:0 0 210px;position:sticky;top:47px;max-height:calc(100vh - 47px);overflow:auto;padding:14px 10px 40px;border-right:1px solid var(--line)}}
.grp{{color:var(--dim);font-size:12px;margin:14px 8px 4px;letter-spacing:.05em}}
.item{{padding:6px 10px;border-radius:7px;cursor:pointer;font-size:14px}}
.item:hover{{background:var(--line)}}
.item.on{{background:var(--acc);color:#fff}}
main{{flex:1;min-width:0;padding:18px 26px 80px}}
.page{{display:none}}
.page.on{{display:block}}
h1{{font-size:22px;margin:.2em 0 .6em}} h2{{font-size:17px;margin:1.4em 0 .5em}} h3{{font-size:15.5px;margin:1.2em 0 .4em}}
ul{{padding-left:22px}} li{{margin:3px 0}} li.sub{{list-style:circle}} .sec{{color:var(--dim);font-size:12.5px;margin-left:6px}}
table{{border-collapse:collapse;margin:10px 0;font-size:14px;width:auto;max-width:100%}}
th,td{{border:1px solid var(--line);padding:6px 11px;text-align:left;vertical-align:top}}
th{{background:var(--card);font-weight:600}}
pre{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto;font-size:13px}}
code{{background:var(--card);padding:1px 5px;border-radius:4px;font-size:13.5px}}
blockquote{{border-left:3px solid var(--acc);margin:10px 0;padding:2px 0 2px 14px;color:var(--dim)}}
strong{{font-weight:650}}
a{{color:var(--acc)}}
input[type=checkbox]{{margin-right:5px}}
</style></head><body>
<header><b>大学看板</b><span>{today.isoformat()} {data["weekday"]} · 第 {data["week"]} 教学周 · 生成于 {data["generated"]}</span></header>
<div class="wrap"><nav>{"".join(nav)}</nav><main>{page_html}</main></div>
<script>
function show(id){{document.querySelectorAll('.page').forEach(e=>e.classList.toggle('on',e.id===id));
document.querySelectorAll('.item').forEach(e=>e.classList.toggle('on',e.dataset.id===id));
try{{localStorage.setItem('kanban-last',id)}}catch(e){{}}}}
document.querySelectorAll('.item').forEach(e=>e.onclick=()=>show(e.dataset.id));
var last='today';try{{last=localStorage.getItem('kanban-last')||'today'}}catch(e){{}}
if(!document.getElementById(last))last='today';
show(last);
</script></body></html>"""

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(doc)
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("看板已生成：", OUT_HTML)
    print("数据已生成：", OUT_JSON)
    print(f"今天 {data['today']} {data['weekday']} 第 {data['week']} 周，课 {len(data['classes'])} 节，待办 {len(data['todos'])} 条")
    if missing:
        print("")
        print("!! 以下页面在 DOCS 里登记了，但文件找不到（看板里会是空白页）：")
        for rel, name in missing:
            print(f"   - {name}  →  {rel}")
        print("   路径写错了，还是文件被删了？改 DOCS 或补齐文件。")
    if "--open" in sys.argv:
        try:
            os.startfile(OUT_HTML)
        except Exception:
            pass


if __name__ == "__main__":
    main()
