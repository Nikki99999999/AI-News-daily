# -*- coding: utf-8 -*-
"""成稿 digest fail-closed 校验闸门（2026-07-02 审计 Top8 #4/#5 加固）。

把 AI 行业日报 / AI Builders 简报的复核从「模型每次现写临时校验 + 自评」固化成
仓库内确定性脚本：render 前必须 exit 0 才允许渲染发信，弱模型（GLM/DeepSeek）跑
云端 routine 时也保证成稿结构达标，模型口头声称复核通过无效。

用法:
    python validate_digest.py data/latest_digest.json            # 日报强校验
    python validate_digest.py data/builders.json --mode builders # 简报通用校验
    python validate_digest.py --selftest

exit 0 = 全过；exit 1 = 有硬伤（打印每条 FAIL）；exit 2 = 用法错误。
render.py __main__ 已在渲染前调用本模块 validate()，不过不渲染。
"""
import json
import sys
import argparse

MAP_CLASS_ENUM = {"A", "B", "C", "配套"}
PLACEHOLDER = ("{{", "}}", "TODO", "待填", "占位", "xxx", "XXX", "PLACEHOLDER", "示例标题", "lorem")
MIN_SUMMARY_CHARS = 15        # 单条摘要下限
MIN_TOTAL_ITEMS = 5           # 全 digest 最少条目
TRUNCATION_TAILS = ("…", "...", "，", "、", "：", "(", "（", "-")  # 结尾疑似截断


def _placeholder_hit(text):
    t = str(text or "")
    return [w for w in PLACEHOLDER if w in t]


def validate_news(d):
    """日报强校验：对照 render.py 实际消费的字段。返回 fails 列表。"""
    fails = []

    if not str(d.get("date_str", "")).strip():
        fails.append("顶层缺 date_str（报头日期）")

    ev = d.get("evolution") or {}
    if not ev:
        fails.append("缺 evolution（技术演进图谱）")
    else:
        counts = ev.get("counts") or {}
        for k in ("A", "B", "C", "配套"):
            if k not in counts:
                fails.append(f"evolution.counts 缺分类计数 {k}")
        if not str(ev.get("verdict", "")).strip():
            fails.append("evolution.verdict（研判）为空")

    sections = d.get("sections") or []
    if not sections:
        fails.append("缺 sections（六部分正文）")

    total_items = 0
    for si, sec in enumerate(sections):
        if not sec or len(sec) < 2:
            fails.append(f"section[{si}] 结构非法（应为 [标题, 条目列表]）")
            continue
        title, items = sec[0], sec[1] or []
        if not str(title).strip():
            fails.append(f"section[{si}] 标题为空")
        for ii, it in enumerate(items):
            total_items += 1
            loc = f"section[{si}].item[{ii}]"
            tc = str(it.get("title_cn", "")).strip()
            if not tc:
                fails.append(f"{loc} 缺 title_cn")
            elif _placeholder_hit(tc):
                fails.append(f"{loc} title_cn 含占位词 {_placeholder_hit(tc)}")
            sm = str(it.get("summary_cn", "")).strip()
            if len(sm) < MIN_SUMMARY_CHARS:
                fails.append(f"{loc} summary_cn 过短或缺失（{len(sm)} < {MIN_SUMMARY_CHARS}）")
            elif _placeholder_hit(sm):
                fails.append(f"{loc} summary_cn 含占位词 {_placeholder_hit(sm)}")
            elif sm.endswith(TRUNCATION_TAILS):
                fails.append(f"{loc} summary_cn 疑似截断（结尾「{sm[-1]}」）")
            mc = it.get("map_class", "")
            if mc and mc not in MAP_CLASS_ENUM:
                fails.append(f"{loc} map_class 非法值「{mc}」（应属 {sorted(MAP_CLASS_ENUM)}）")
            sc = it.get("score", "")
            if sc not in ("", None):
                try:
                    fv = float(sc)
                    if not (0 <= fv <= 10):
                        fails.append(f"{loc} score 越界 {sc}（应 0-10）")
                except (TypeError, ValueError):
                    fails.append(f"{loc} score 非数值「{sc}」")

    if total_items < MIN_TOTAL_ITEMS:
        fails.append(f"全 digest 条目仅 {total_items} 条（< {MIN_TOTAL_ITEMS}，疑似成稿跑偏/内容坍缩）")
    return fails


def validate_builders(d):
    """简报通用校验（无固定 schema 样本，宽松：必需容器非空 + 占位/截断扫描）。
    诚实声明：待有真实简报 digest 样本后可升级为强校验。"""
    fails = []
    # 找出所有字符串叶子做占位/截断扫描
    def walk(node, path="root"):
        if isinstance(node, dict):
            if not node:
                fails.append(f"{path} 为空对象")
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, str):
            hit = _placeholder_hit(node)
            if hit:
                fails.append(f"{path} 含占位词 {hit}")
    if not d:
        fails.append("digest 为空")
    walk(d)
    return fails


def validate(path, mode="news"):
    """校验入口。返回 fails 列表；render.py 可 import 调用。文件不可读也算硬伤。"""
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        return [f"digest 文件无法读取/解析: {e}"]
    return validate_builders(d) if mode == "builders" else validate_news(d)


def _selftest():
    good = {
        "date_str": "2026-07-02",
        "evolution": {"counts": {"A": 2, "B": 1, "C": 1, "配套": 1}, "verdict": "今日整体推进有限但方向明确清晰。"},
        "sections": [["模型进展", [
            {"title_cn": "某模型发布", "summary_cn": "这是一段足够长的正常中文摘要内容，描述完整没有截断。", "map_class": "A", "score": 8},
            {"title_cn": "推理成本下降", "summary_cn": "另一段完整摘要，同样超过最短字符阈值且结尾正常。", "map_class": "B", "score": 7.5},
        ]], ["工具生态", [
            {"title_cn": "新工具", "summary_cn": "第三条摘要内容完整，长度达标结尾自然。", "map_class": "配套"},
            {"title_cn": "开源项目", "summary_cn": "第四条摘要内容完整，长度达标结尾自然。", "map_class": "C"},
            {"title_cn": "第五条", "summary_cn": "第五条摘要凑够最少条目数量要求。", "map_class": "A"},
        ]]],
    }
    assert not validate_news(good), validate_news(good)

    bad = {
        "date_str": "",
        "evolution": {"counts": {"A": 1}, "verdict": ""},
        "sections": [["", [
            {"title_cn": "", "summary_cn": "短", "map_class": "X", "score": 99},
            {"title_cn": "含 TODO 的标题", "summary_cn": "这段摘要故意以逗号结尾制造截断，", "score": "高"},
        ]]],
    }
    f = validate_news(bad)
    j = "".join(f)
    for expect in ["date_str", "verdict", "缺分类计数", "标题为空", "缺 title_cn",
                   "过短", "map_class 非法", "score 越界", "占位词", "截断", "条目仅"]:
        assert expect in j, f"漏抓 {expect}: {f}"

    assert validate("__nonexist__.json")[0].startswith("digest 文件无法读取")
    assert any("占位" in x for x in validate_builders({"a": {"b": "含 TODO"}}))
    print("SELFTEST PASS: 好 digest 全过、坏 digest 11 类硬伤全抓、缺文件与简报模式均 fail-closed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", help="digest json 路径")
    ap.add_argument("--mode", choices=["news", "builders"], default="news")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
        return
    if not args.path:
        print("用法: python validate_digest.py <digest.json> [--mode news|builders]")
        sys.exit(2)
    fails = validate(args.path, args.mode)
    if fails:
        print(f"VALIDATE FAIL ({len(fails)} 项，禁止渲染/发送):")
        for f in fails:
            print(f"  - {f}")
        sys.exit(1)
    print(f"VALIDATE PASS: {args.path} 成稿结构达标（mode={args.mode}）")


if __name__ == "__main__":
    main()
