"""家里这些药的底细：通用名、别名、成分、类别。

只收常见非处方药和几类处方药常识，不涉及剂量、疗程和适应症判断——
那不是这个工具该干的活。这里唯一要做的是三件事：
把商品名对回成分、把同一成分的药认出来、把不能一起吃的组合标出来。
"""

from __future__ import annotations

# 每条：name 通用名/大类，aliases 商品名，ingredients 成分，kind 类别，tags 标记
MEDS: list[dict] = [
    # ---- 解热镇痛 ----
    {"name": "对乙酰氨基酚", "aliases": ["泰诺林", "必理通", "扑热息痛", "百服宁", "醋氨酚"],
     "ingredients": ["对乙酰氨基酚"], "kind": "解热镇痛", "tags": ["otc"]},
    {"name": "布洛芬", "aliases": ["芬必得", "美林", "布洛芬缓释胶囊", "优思弗"],
     "ingredients": ["布洛芬"], "kind": "解热镇痛", "tags": ["otc", "伤胃"]},
    {"name": "双氯芬酸", "aliases": ["扶他林", "双氯芬酸钠", "戴芬"],
     "ingredients": ["双氯芬酸"], "kind": "解热镇痛", "tags": ["处方", "伤胃"]},
    {"name": "阿司匹林", "aliases": ["拜阿司匹灵", "乙酰水杨酸"],
     "ingredients": ["阿司匹林"], "kind": "解热镇痛/抗血小板", "tags": ["处方", "伤胃"]},
    # ---- 复方感冒药（这一条最要命：商品名各不相同，成分都是对乙酰氨基酚）----
    {"name": "复方感冒药", "aliases": ["999感冒灵", "感冒灵颗粒", "白加黑", "新康泰克", "快克", "感康", "泰诺", "日夜百服宁"],
     "ingredients": ["对乙酰氨基酚", "马来酸氯苯那敏"], "kind": "感冒药", "tags": ["otc", "含扑尔敏"]},
    # ---- 抗过敏 ----
    {"name": "氯雷他定", "aliases": ["开瑞坦", "百为坦"],
     "ingredients": ["氯雷他定"], "kind": "抗过敏", "tags": ["otc"]},
    {"name": "西替利嗪", "aliases": ["仙特明", "西可韦"],
     "ingredients": ["西替利嗪"], "kind": "抗过敏", "tags": ["otc"]},
    {"name": "马来酸氯苯那敏", "aliases": ["扑尔敏"],
     "ingredients": ["马来酸氯苯那敏"], "kind": "抗过敏", "tags": ["otc", "嗜睡"]},
    # ---- 抗感染 ----
    {"name": "阿莫西林", "aliases": ["阿莫仙", "羟氨苄青霉素"],
     "ingredients": ["阿莫西林"], "kind": "抗生素", "tags": ["处方"]},
    {"name": "头孢类", "aliases": ["头孢", "头孢克肟", "头孢拉定", "头孢呋辛", "先锋"],
     "ingredients": ["头孢类"], "kind": "抗生素", "tags": ["处方", "忌酒"]},
    {"name": "甲硝唑", "aliases": ["灭滴灵", "甲硝唑片"],
     "ingredients": ["甲硝唑"], "kind": "抗感染", "tags": ["处方", "忌酒"]},
    # ---- 肠胃 ----
    {"name": "蒙脱石散", "aliases": ["思密达", "肯特令"],
     "ingredients": ["蒙脱石"], "kind": "止泻", "tags": ["otc"]},
    {"name": "口服补液盐", "aliases": ["补液盐", "ORS"],
     "ingredients": ["氯化钠", "氯化钾", "葡萄糖"], "kind": "补液", "tags": ["otc"]},
    {"name": "奥美拉唑", "aliases": ["洛赛克", "奥克"],
     "ingredients": ["奥美拉唑"], "kind": "抑酸", "tags": ["处方"]},
    {"name": "铝碳酸镁", "aliases": ["达喜", "胃达喜"],
     "ingredients": ["铝碳酸镁"], "kind": "抗酸", "tags": ["otc"]},
    {"name": "多潘立酮", "aliases": ["吗丁啉"],
     "ingredients": ["多潘立酮"], "kind": "促胃动力", "tags": ["otc"]},
    # ---- 慢病 ----
    {"name": "二甲双胍", "aliases": ["格华止", "美迪康"],
     "ingredients": ["二甲双胍"], "kind": "降糖", "tags": ["处方"]},
    {"name": "氨氯地平", "aliases": ["络活喜", "压氏达"],
     "ingredients": ["氨氯地平"], "kind": "降压", "tags": ["处方"]},
    {"name": "硝苯地平", "aliases": ["拜新同", "心痛定"],
     "ingredients": ["硝苯地平"], "kind": "降压", "tags": ["处方"]},
    {"name": "缬沙坦", "aliases": ["代文"],
     "ingredients": ["缬沙坦"], "kind": "降压", "tags": ["处方"]},
    # ---- 中成药与含酒精制剂 ----
    {"name": "藿香正气水", "aliases": ["藿香正气液"],
     "ingredients": ["乙醇", "广藿香"], "kind": "中成药", "tags": ["含酒精"]},
    {"name": "十滴水", "aliases": [],
     "ingredients": ["乙醇"], "kind": "中成药", "tags": ["含酒精"]},
    # ---- 外用 ----
    {"name": "碘伏", "aliases": ["碘伏消毒液", "聚维酮碘"],
     "ingredients": ["聚维酮碘"], "kind": "外用消毒", "tags": ["外用"]},
    {"name": "创可贴", "aliases": ["止血贴", "邦迪"],
     "ingredients": [], "kind": "外用敷料", "tags": ["外用"]},
    {"name": "红霉素软膏", "aliases": ["红霉素眼膏"],
     "ingredients": ["红霉素"], "kind": "外用抗菌", "tags": ["外用"]},
    # ---- 营养补充 ----
    {"name": "维生素C", "aliases": ["维C", "抗坏血酸"],
     "ingredients": ["维生素C"], "kind": "维生素", "tags": ["otc"]},
    {"name": "复合维生素", "aliases": ["多维元素片", "善存", "21金维他"],
     "ingredients": ["维生素A", "维生素B族", "维生素C", "维生素D", "维生素E"],
     "kind": "维生素", "tags": ["otc"]},
]

# 不能碰的组合。为什么写在这里而不是让模型说：这是说明书级别的硬事实。
# a 是一个集合（通用名），b 也是集合或者 b_tags（标记）；through_ingredient=True 时
# 还要求两边成分真的重叠——只是"都叫解热镇痛"不算重复吃。
CONFLICTS: list[dict] = [
    {"a": ["头孢类", "甲硝唑"], "b": [], "b_tags": ["含酒精"],
     "why": "头孢/甲硝唑遇上酒精可能引起双硫仑样反应：脸红、心悸、血压下降，严重会休克。",
     "level": "high"},
    {"a": ["复方感冒药", "对乙酰氨基酚"], "b": ["对乙酰氨基酚"], "through_ingredient": True,
     "why": "复方感冒药里通常已经含对乙酰氨基酚，再单独吃退烧药等于同一成分加倍。",
     "level": "high"},
    {"a": ["布洛芬", "双氯芬酸", "阿司匹林"], "b": ["布洛芬", "双氯芬酸", "阿司匹林"],
     "through_ingredient": False,
     "why": "两种以上非甾体抗炎药同用，胃出血风险明显增加。",
     "level": "high"},
    {"a": ["氯雷他定", "西替利嗪", "马来酸氯苯那敏"], "b": [], "b_tags": ["嗜睡"],
     "why": "抗过敏药叠加会加重嗜睡，别在开车或操作机器前吃。",
     "level": "medium"},
]

_SPACE = " \t　"


def normalize(name: str) -> str:
    return (name or "").strip().strip(_SPACE).replace("（", "(").replace("）", ")")


def lookup(name: str) -> dict | None:
    """商品名 → 通用条目。按名字、别名、包含关系三级找。"""
    key = normalize(name)
    if not key:
        return None
    for med in MEDS:
        if key == med["name"]:
            return {**med, "matched": "exact"}
        for alias in med["aliases"]:
            if key == normalize(alias):
                return {**med, "matched": "alias"}
    best = None
    for med in MEDS:
        for cand in [med["name"]] + list(med["aliases"]):
            c = normalize(cand)
            if c and (c in key or key in c):
                if best is None or len(c) > best[0]:
                    best = (len(c), med)
    if best:
        return {**best[1], "matched": "fuzzy"}
    return None


def all_ingredients(med: dict) -> list[str]:
    return list(med.get("ingredients") or [])


def describe(name: str) -> str:
    med = lookup(name)
    if not med:
        return f"{name}（库里没有）"
    return f"{name} → {med['name']}（{med['kind']}，成分：{'、'.join(med['ingredients']) or '无'}）"
