"""检查药箱：过期、快过期、重复成分、危险组合、库存不足。

全部走本地规则，不调模型——这些是查得到的事实，让模型说反而不稳。
模型在 advice.py 里另管一块：给出管理人话建议。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from . import drugs

EXPIRING_DAYS = 60
# 只报「真的没有了」。默认 2 时，家里每盒只剩 1 片的药会全被列进"快用完"，
# 十条警告里九条是噪音——警告多了等于没有警告。
LOW_STOCK = 0
DAYS = ("days", "days_left", "days_ago")


def parse_date(text: str) -> date | None:
    text = (text or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d", "%Y-%m"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _hit(med: dict, names: list[str], tags: list[str]) -> bool:
    if med["name"] in names:
        return True
    if tags and set(med.get("tags") or []) & set(tags):
        return True
    return False


def check(items: list[dict], today: date | None = None, low_stock: int = LOW_STOCK) -> dict:
    today = today or date.today()
    expired, expiring, low_stock_items, unknown = [], [], [], []
    resolved = []

    for item in items:
        name = (item.get("name") or "").strip()
        med = drugs.lookup(name)
        if not med:
            unknown.append(name)
            continue
        resolved.append({"raw": item, "med": med})

        exp = parse_date(item.get("expire") or "")
        if exp:
            left = (exp - today).days
            if left < 0:
                expired.append({"name": name, "generic": med["name"], "expire": exp.isoformat(),
                                "days_ago": -left})
            elif left <= EXPIRING_DAYS:
                expiring.append({"name": name, "generic": med["name"], "expire": exp.isoformat(),
                                 "days_left": left})

        qty = item.get("qty")
        if isinstance(qty, (int, float)) and qty <= low_stock:
            low_stock_items.append({"name": name, "qty": qty})

    # 重复成分：同一成分出现在两个及以上不同的药
    by_ingredient: dict[str, set[str]] = {}
    for entry in resolved:
        for ing in drugs.all_ingredients(entry["med"]):
            by_ingredient.setdefault(ing, set()).add(entry["raw"].get("name") or "")
    duplicates = [
        {"ingredient": ing, "names": sorted(names)}
        for ing, names in sorted(by_ingredient.items())
        if len(names) > 1
    ]

    # 危险组合：按规则扫所有药对
    conflicts = []
    names = [(e["raw"].get("name") or "", e["med"]) for e in resolved]
    for rule in drugs.CONFLICTS:
        for i in range(len(names)):
            for j in range(len(names)):
                if i == j:
                    continue
                a_name, a_med = names[i]
                b_name, b_med = names[j]
                if not _hit(a_med, rule["a"], []):
                    continue
                if not _hit(b_med, rule.get("b") or [], rule.get("b_tags") or []):
                    continue
                if b_med["name"] == a_med["name"]:
                    continue
                if rule.get("through_ingredient"):
                    shared = set(drugs.all_ingredients(a_med)) & set(drugs.all_ingredients(b_med))
                    if not shared:
                        continue
                    why = rule["why"] + f"（两边都有：{'、'.join(sorted(shared))}）"
                else:
                    why = rule["why"]
                conflicts.append({
                    "a": a_name, "b": b_name, "a_generic": a_med["name"],
                    "b_generic": b_med["name"], "why": why, "level": rule["level"],
                })

    # 同一对药只留一条
    seen, unique = set(), []
    for c in conflicts:
        key = tuple(sorted([c["a"], c["b"]])) + (c["why"],)
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)

    level = "ok"
    if expired or any(c["level"] == "high" for c in unique):
        level = "high"
    elif expiring or unique or duplicates:
        level = "medium"

    return {
        "as_of": today.isoformat(),
        "expired": expired,
        "expiring": expiring,
        "duplicates": duplicates,
        "conflicts": unique,
        "low_stock": low_stock_items,
        "unknown": unknown,
        "level": level,
        "checked": len(items),
    }


def labels(level: str) -> str:
    return {"high": "有硬问题，先处理", "medium": "有要留意的", "ok": "看着还行"}.get(level, level)


def summary_line(result: dict) -> str:
    bits = []
    if result["expired"]:
        bits.append(f"过期 {len(result['expired'])} 个")
    if result["expiring"]:
        bits.append(f"{EXPIRING_DAYS} 天内到期 {len(result['expiring'])} 个")
    if result["duplicates"]:
        bits.append(f"重复成分 {len(result['duplicates'])} 项")
    if result["conflicts"]:
        bits.append(f"不宜同用 {len(result['conflicts'])} 对")
    if result["low_stock"]:
        bits.append(f"已经用完 {len(result['low_stock'])} 个")
    if result["unknown"]:
        bits.append(f"认不出 {len(result['unknown'])} 个")
    return "、".join(bits) if bits else "没查出问题"


def _with_generic(name: str, generic: str) -> str:
    return name if not generic or name == generic else f"{name}（{generic}）"


def render_text(result: dict) -> str:
    lines = [f"检查于 {result['as_of']} · {result['checked']} 条 · {labels(result['level'])}"
             f" · {summary_line(result)}"]
    if result["expired"]:
        lines.append("")
        lines.append("过期了，别吃：")
        for e in result["expired"]:
            lines.append(f"  · {_with_generic(e['name'], e['generic'])} — 过期 {e['days_ago']} 天，{e['expire']}")
    if result["expiring"]:
        lines.append("")
        lines.append(f"{EXPIRING_DAYS} 天内到期：")
        for e in result["expiring"]:
            lines.append(f"  · {e['name']} — 还剩 {e['days_left']} 天，{e['expire']}")
    if result["duplicates"]:
        lines.append("")
        lines.append("同一成分出现在好几盒里（一起吃等于加量）：")
        for d in result["duplicates"]:
            lines.append(f"  · {d['ingredient']}：{'、'.join(d['names'])}")
    if result["conflicts"]:
        lines.append("")
        lines.append("不宜同用：")
        for c in result["conflicts"]:
            lines.append(f"  · [{c['level']}] {c['a']} + {c['b']}")
            lines.append(f"    {c['why']}")
    if result["low_stock"]:
        lines.append("")
        lines.append("已经用完了：")
        for s in result["low_stock"]:
            lines.append(f"  · {s['name']} 剩 {s['qty']:g}")
    if result["unknown"]:
        lines.append("")
        lines.append(f"库里没有，没参与检查：{'、'.join(result['unknown'])}")
    return "\n".join(lines)


def deadline_hint(today: date | None = None) -> date:
    return (today or date.today()) + timedelta(days=EXPIRING_DAYS)
