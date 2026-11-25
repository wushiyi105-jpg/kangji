"""命令行入口。"""

from __future__ import annotations

import argparse
import json
import os

from . import advice, check, drugs, store

_OPENED: list = []


def _open(args):
    conn = store.connect(args.db)
    _OPENED.append(conn)
    return conn


def cmd_add(args) -> int:
    conn = _open(args)
    med = drugs.lookup(args.name)
    expire = check.parse_date(args.expire)
    if args.expire and not expire:
        print(f"✗ 有效期看不懂：{args.expire}（写成 2027-08 或 2027-08-31）")
        return 1
    mid = store.add_med(conn, args.name, med["name"] if med else "", args.qty,
                        expire.isoformat() if expire else "", args.place or "", args.note or "")
    if med:
        print(f"· [{mid}] {args.name} → {med['name']}（{med['kind']}，成分 {'、'.join(med['ingredients']) or '无'}）")
    else:
        print(f"· [{mid}] {args.name} 已记下，但药库里没这个名字，检查时会跳过它")
    print(f"  数量 {args.qty}，有效期 {expire.isoformat() if expire else '没记'}，位置 {args.place or '没记'}")
    return 0


def cmd_import(args) -> int:
    """从 CSV 批量导入：表头要能认出来（名称/数量/有效期/位置）。"""
    import csv

    conn = _open(args)
    if not os.path.isfile(args.csv):
        print(f"✗ 找不到文件：{args.csv}")
        return 1
    with open(args.csv, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("✗ CSV 里没有数据行")
        return 1

    added, skipped = 0, 0
    for row in rows:
        keys = {k.strip(): (v or "").strip() for k, v in row.items() if k}
        name = keys.get("名称") or keys.get("药名") or keys.get("name") or ""
        if not name:
            skipped += 1
            continue
        try:
            qty = float(keys.get("数量") or keys.get("qty") or 1)
        except ValueError:
            qty = 1.0
        expire_text = keys.get("有效期") or keys.get("expire") or ""
        expire = check.parse_date(expire_text)
        if expire_text and not expire:
            print(f"  ! {name} 的有效期看不懂（{expire_text}），按没记处理")
        med = drugs.lookup(name)
        store.add_med(conn, name, med["name"] if med else "", qty,
                      expire.isoformat() if expire else "",
                      keys.get("位置") or keys.get("place") or "",
                      keys.get("备注") or keys.get("note") or "")
        added += 1
    print(f"· 导入 {added} 条" + (f"，跳过 {skipped} 条（没写名称）" if skipped else ""))
    print("  跑检查：python -m kangji check")
    return 0


def cmd_list(args) -> int:
    conn = _open(args)
    rows = store.list_meds(conn)
    if not rows:
        print("药箱是空的。先 python -m kangji add 布洛芬 --qty 1 --expire 2027-06")
        return 0
    print(f"{'ID':<4}{'数量':<7}{'有效期':<13}{'位置':<10}名字")
    for r in rows:
        print(f"{r['id']:<4}{r['qty']:<7}{r['expire'] or '没记':<13}{r['place'] or '-':<10}{r['name']}")
    return 0


def cmd_check(args) -> int:
    conn = _open(args)
    rows = store.list_meds(conn)
    if not rows:
        print("药箱是空的，没什么可查的。")
        return 0
    result = check.check(rows, today=check.parse_date(args.today) if args.today else None,
                         low_stock=args.low_stock)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print(check.render_text(result))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(check.render_text(result) + "\n")
        print(f"\n已写到 {args.out}")
    return 0


def cmd_advice(args) -> int:
    conn = _open(args)
    rows = store.list_meds(conn)
    if not rows:
        print("药箱是空的，先记几样再问。")
        return 0
    result = check.check(rows, today=check.parse_date(args.today) if args.today else None)
    print(check.render_text(result))
    print("\n问模型要管理建议…（十几秒）", flush=True)

    cfg = None
    if args.api_key or args.base_url or args.model:
        cfg = {}
        if args.api_key:
            cfg["api_key"] = args.api_key
        if args.base_url:
            cfg["base_url"] = args.base_url
        if args.model:
            cfg["model"] = args.model

    out = advice.advise(result, rows, config=cfg)
    print("\n" + advice.render_text(out))
    if out["error"] and not out["actions"]:
        return 0
    store.save_advice(conn, out["actions"], out["summary"], out["foreign"])
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_use(args) -> int:
    conn = _open(args)
    if not store.get_med(conn, args.id):
        print(f"✗ 没有 id={args.id} 的药")
        return 1
    left = store.use_med(conn, args.id, args.n)
    print(f"· 用掉 {args.n}，剩 {left:g}" + ("（用完了，记得补或删掉这条）" if left == 0 else ""))
    return 0


def cmd_show(args) -> int:
    conn = _open(args)
    row = store.get_med(conn, args.id)
    if not row:
        print(f"✗ 没有 id={args.id} 的药")
        return 1
    med = drugs.lookup(row["name"])
    print(f"=== [{row['id']}] {row['name']} ===")
    if med:
        print(f"通用名 {med['name']} · {med['kind']} · 成分 {'、'.join(med['ingredients']) or '无'}")
        print(f"标记：{'、'.join(med['tags']) or '无'}")
    else:
        print("药库里没有这个名字")
    print(f"数量 {row['qty']}，有效期 {row['expire'] or '没记'}，位置 {row['place'] or '没记'}")
    if row["note"]:
        print(f"备注：{row['note']}")
    return 0


def cmd_rm(args) -> int:
    conn = _open(args)
    if not store.get_med(conn, args.id):
        print(f"✗ 没有 id={args.id} 的药")
        return 1
    store.delete_med(conn, args.id)
    print(f"· [{args.id}] 已删除")
    return 0


def cmd_stats(args) -> int:
    conn = _open(args)
    print("统计：", store.stats(conn))
    return 0


def cmd_serve(args) -> int:
    from . import web

    conn = _open(args)
    web.serve(conn, host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kangji", description="家庭药箱：过期、重复成分、不宜同用。")
    p.add_argument("--db", default="data/kangji.db")
    p.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    p.add_argument("--api-key")
    p.add_argument("--base-url")
    p.add_argument("--model")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="记一盒药")
    a.add_argument("name")
    a.add_argument("--qty", type=float, default=1)
    a.add_argument("--expire", default="")
    a.add_argument("--place", default="")
    a.add_argument("--note", default="")
    a.set_defaults(func=cmd_add)

    im = sub.add_parser("import", help="从 CSV 批量导入")
    im.add_argument("csv")
    im.set_defaults(func=cmd_import)

    sub.add_parser("list", help="药箱清单").set_defaults(func=cmd_list)

    c = sub.add_parser("check", help="跑一遍检查")
    c.add_argument("--today", help="把今天当作哪天（测试用），如 2027-01-01")
    c.add_argument("--low-stock", type=float, default=check.LOW_STOCK,
                   help="数量低于等于这个值就报「用完」，默认 0（只报真的没了）")
    c.add_argument("--json", action="store_true")
    c.add_argument("--out")
    c.set_defaults(func=cmd_check)

    adv = sub.add_parser("advice", help="问模型要管理建议")
    adv.add_argument("--today")
    adv.add_argument("--json", action="store_true")
    adv.set_defaults(func=cmd_advice)

    u = sub.add_parser("use", help="用掉几个")
    u.add_argument("id", type=int)
    u.add_argument("--n", type=float, default=1)
    u.set_defaults(func=cmd_use)

    s = sub.add_parser("show", help="看一盒的详情")
    s.add_argument("id", type=int)
    s.set_defaults(func=cmd_show)

    r = sub.add_parser("rm", help="删一盒")
    r.add_argument("id", type=int)
    r.set_defaults(func=cmd_rm)

    sub.add_parser("stats", help="统计").set_defaults(func=cmd_stats)

    sv = sub.add_parser("serve", help="起 Web")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8772)
    sv.set_defaults(func=cmd_serve)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    finally:
        while _OPENED:
            try:
                _OPENED.pop().close()
            except Exception:  # noqa: BLE001
                pass
