"""让模型给药箱管理人话建议。

边界写死在提示词里：不做诊断、不提剂量、不推荐"你该吃什么药"。
只讲怎么管：先处理哪个、哪些别放一起、什么情况该去医院。

还有一道核验：它嘴里冒出来的药名必须是你药箱里真有的。
模型很爱顺口加一句"可以配合布洛芬"，哪怕你箱子里压根没有布洛芬。
"""

from __future__ import annotations

from . import drugs, llm

MAX_ACTIONS = 5

SYSTEM = """你是家庭药箱的管理顾问，不是医生。

能说的：
- 哪些先处理（过期的、快过期的、重复的、不能放一起的）
- 怎么收纳（外用药和内服药分开、原包装保留、避光避潮）
- 什么情况下别自己处理、直接去医院

不能说的：
- 不诊断、不判断病情、不说「你这是xx病」
- 不给剂量、不给疗程、不推荐新增什么药
- 不评价某个药「效果好/不好」

硬规则：提到的药名必须是清单里出现过的。清单里没有的药，一个字都不要提。
拿不准就写「按说明书」或「问药师」。

只输出 JSON：
{"actions": [{"n": 1, "thing": "", "why": ""}],
 "summary": "两句话以内"}"""


def find_foreign_meds(text: str, allowed_generics: set[str]) -> list[str]:
    """找出文本里提到、但不在药箱清单里的药名。"""
    hits = []
    for med in drugs.MEDS:
        if med["name"] in allowed_generics:
            continue
        for cand in [med["name"]] + list(med["aliases"]):
            if cand and len(cand) >= 2 and cand in (text or ""):
                hits.append(cand)
                break
    return hits


def build_prompt(result: dict, items: list[dict]) -> tuple[str, set[str]]:
    """把药箱和规则结论整理成提示词，同时返回「允许提到的药名」集合。"""
    allowed = set()
    lines = []
    for item in items:
        med = drugs.lookup(item.get("name") or "")
        name = item.get("name") or ""
        if med:
            allowed.add(med["name"])
            lines.append(f"- {name}（{med['name']}，{med['kind']}）"
                         f" 数量 {item.get('qty')}，有效期 {item.get('expire') or '没记'}")
        else:
            lines.append(f"- {name}（药库里没有这个，别对它下判断）")

    situation = []
    if result["expired"]:
        situation.append("过期：" + "、".join(e["name"] for e in result["expired"]))
    if result["expiring"]:
        situation.append(f"{len(result['expiring'])} 个 60 天内到期")
    for d in result["duplicates"]:
        situation.append(f"{d['ingredient']} 重复出现在 {'、'.join(d['names'])}")
    for c in result["conflicts"]:
        situation.append(f"{c['a']} 与 {c['b']} 不宜同用")
    if not situation:
        situation.append("规则检查没发现问题")

    user = ("【药箱清单】\n" + "\n".join(lines) +
            "\n\n【规则已经查出来的】\n" + "\n".join(f"- {s}" for s in situation) +
            "\n\n按上述边界，给这份药箱的管理建议，输出 JSON。")
    return user, allowed


def advise(result: dict, items: list[dict], config=None, max_tokens: int = 8000) -> dict:
    """返回 {actions, summary, error, foreign}。失败不抛。"""
    user, allowed = build_prompt(result, items)

    try:
        raw = llm.chat(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            config=config, temperature=0.3, max_tokens=max_tokens,
        )
        data = llm.extract_json(raw)
        if not isinstance(data, dict):
            raise llm.LLMError("返回不是对象")
    except llm.LLMError as e:
        return {"actions": [], "summary": "", "error": str(e), "foreign": []}

    foreign = []
    actions = []
    for row in data.get("actions") or []:
        if not isinstance(row, dict):
            continue
        thing = str(row.get("thing") or "").strip()
        why = str(row.get("why") or "").strip()
        if not thing:
            continue
        bad = find_foreign_meds(thing + " " + why, allowed)
        if bad:
            foreign.extend(bad)
        # 编号一律由我们重排：模型给的 n 经常缺失、重复，或者干脆从 0 开始
        actions.append({"n": len(actions) + 1, "thing": thing[:200],
                        "why": why[:200], "foreign": bad})

    summary = str(data.get("summary") or "").strip()
    foreign.extend(find_foreign_meds(summary, allowed))
    foreign = list(dict.fromkeys(foreign))  # 同一条在 action 和 summary 里各出现一次，只提示一次
    return {"actions": actions[:MAX_ACTIONS], "summary": summary[:200],
            "error": "", "foreign": foreign}


def render_text(out: dict) -> str:
    if out.get("error") and not out.get("actions"):
        return f"✗ 模型没给建议：{out['error']}"
    lines = []
    if out.get("error"):
        lines.append(f"! 输出没解析完：{out['error']}")
    lines.append("=== 管理建议 ===")
    for a in out["actions"]:
        lines.append(f"{a['n']}. {a['thing']}")
        if a["why"]:
            lines.append(f"   {a['why']}")
        if a["foreign"]:
            lines.append(f"   ! 这里提到了药箱里没有的药：{'、'.join(a['foreign'])}")
    if out["summary"]:
        lines.append("")
        lines.append(out["summary"])
    if out["foreign"]:
        lines.append("")
        lines.append(f"! 共提到 {len(out['foreign'])} 处药箱外的药名（{'、'.join(out['foreign'])}），别照着买")
    return "\n".join(lines)
