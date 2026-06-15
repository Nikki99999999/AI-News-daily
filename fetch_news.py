# -*- coding: utf-8 -*-
"""
AI 行业重大新闻日报 —— 抓取层（零依赖，仅 Python stdlib）

职责（学 tech-digest 的分工）：脚本只负责"抓取 + 解析 + 时间过滤 + 跨源去重 + 输出结构化数据"，
不做定性判断。重大性两段式打分、三限制地图归类、QA Gate、成稿，全部交给上层 Claude（SKILL.md）。

输出：data_news_{date}.json —— 结构化条目数组，每条带 source_tier / 多源计数 / 热度提示，供 agent 打分。

用法：
    python fetch_news.py            # 默认抓最近 36 小时
    python fetch_news.py --hours 24
    python fetch_news.py --hours 48 --out data.json
"""
import sys, os, json, re, ssl, html, argparse, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

# 泛科技源需做 AI 关键词过滤（这些源混有非 AI 内容）；GNews/官方源本身已限定 AI 不过滤
NEED_AI_FILTER = {"36Kr快讯", "IT之家"}
AI_KW = re.compile(
    r"AI|人工智能|大模型|大語言|语言模型|模型|LLM|GPT|Claude|Gemini|Llama|OpenAI|Anthropic|"
    r"算力|智能体|Agent|英伟达|NVIDIA|芯片|AIGC|生成式|机器学习|深度学习|神经网络|训练|推理|"
    r"DeepSeek|通义|文心|豆包|Kimi|智谱|月之暗面|MiniMax|具身|多模态|扩散|Transformer",
    re.I)
# 每源上限：arXiv 论文多且非"新闻"，单独限；其余源统一上限，把候选压到百级
PER_SOURCE_CAP = {"arXiv cs.AI": 40}
DEFAULT_CAP = 25
HN_MIN_POINTS = 15  # HackerNews 热度门槛


def gnews(q, lang="zh"):
    qq = urllib.parse.quote(q)
    loc = "hl=zh-CN&gl=CN&ceid=CN:zh" if lang == "zh" else "hl=en-US&gl=US&ceid=US:en"
    return f"https://news.google.com/rss/search?q={qq}&{loc}"


# (名称, 类型, url, source_tier)   tier: 1=官方一手 2=一线媒体 3=中文/聚合 4=学术社区
SOURCES = [
    ("OpenAI",            "rss",   "https://openai.com/news/rss.xml", 1),
    ("Google DeepMind",   "rss",   "https://deepmind.google/blog/rss.xml", 1),
    ("Google AI",         "rss",   "https://blog.google/technology/ai/rss/", 1),
    ("HuggingFace",       "rss",   "https://huggingface.co/blog/feed.xml", 1),
    ("Microsoft Research","rss",   "https://www.microsoft.com/en-us/research/feed/", 1),
    ("Anthropic",         "gnews", gnews("Anthropic Claude", "en"), 1),
    ("Meta AI",           "gnews", gnews("Meta AI Llama OR Meta superintelligence", "en"), 1),
    ("Mistral",           "gnews", gnews("Mistral AI", "en"), 1),
    ("TechCrunch AI",     "rss",   "https://techcrunch.com/category/artificial-intelligence/feed/", 2),
    ("Ars Technica AI",   "rss",   "https://arstechnica.com/ai/feed/", 2),
    ("MIT Tech Review",   "rss",   "https://www.technologyreview.com/topic/artificial-intelligence/feed/", 2),
    ("The Verge AI",      "rss",   "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", 2),
    ("The Decoder",       "rss",   "https://the-decoder.com/feed/", 2),
    ("IT之家",             "rss",   "https://www.ithome.com/rss/", 3),
    ("36Kr快讯",           "rss",   "https://36kr.com/feed-newsflash", 3),
    ("机器之心",            "gnews", gnews("机器之心", "zh"), 3),
    ("量子位",             "gnews", gnews("量子位", "zh"), 3),
    ("中文AI聚合",          "gnews", gnews("人工智能 OR 大模型 OR AI模型", "zh"), 3),
    ("中文AI融资",          "gnews", gnews("AI 融资 OR 大模型 融资 OR AI 收购", "zh"), 3),
    ("arXiv cs.AI",       "rss",   "http://export.arxiv.org/rss/cs.AI", 4),
    ("HackerNews AI",     "hn",    "https://hn.algolia.com/api/v1/search?tags=story&query=AI%20OR%20LLM%20OR%20GPT&hitsPerPage=60", 4),
]


def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
        "Accept": "application/rss+xml,application/xml,text/xml,application/json,*/*"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read()


def clean(s):
    if not s:
        return ""
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s, flags=re.S)
    s = html.unescape(s)                   # 先解码实体（GNews 用 &lt;a&gt; 包 HTML）
    s = re.sub(r"<[^>]+>", "", s)          # 再去标签
    s = html.unescape(s)                   # 再解码一次，防双重编码
    return re.sub(r"\s+", " ", s).strip()


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)       # RFC822 (pubDate)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except Exception:
        pass
    try:                                    # ISO8601 (Atom)
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except Exception:
        return None


def parse_xml_items(txt):
    """返回 [(title, link, date_str, summary)]，兼容 RSS <item> 与 Atom <entry>。"""
    out = []
    blocks = re.findall(r"<item[ >].*?</item>", txt, re.S) or re.findall(r"<entry[ >].*?</entry>", txt, re.S)
    for b in blocks:
        t = re.search(r"<title[^>]*>(.*?)</title>", b, re.S)
        # link: RSS <link>text</link> 或 Atom <link href="..."/>
        l = re.search(r"<link[^>]*>(.*?)</link>", b, re.S)
        link = clean(l.group(1)) if l else ""
        if not link:
            lh = re.search(r'<link[^>]*href="([^"]+)"', b)
            link = lh.group(1) if lh else ""
        d = re.search(r"<(?:pubDate|published|updated|dc:date)>(.*?)</", b, re.S)
        s = re.search(r"<(?:description|summary|content:encoded|content)[^>]*>(.*?)</(?:description|summary|content:encoded|content)>", b, re.S)
        out.append((clean(t.group(1)) if t else "", link,
                    d.group(1).strip() if d else "", clean(s.group(1)) if s else ""))
    return out


def fetch(name, typ, url, tier, cutoff):
    try:
        items = []
        if typ == "hn":
            # search_by_date 按时间倒序 + numericFilters 限时间窗，避免 search 返回历史高分帖
            ts = int(cutoff.timestamp())
            # Algolia 不支持 query 里的布尔 OR（会被当字面词）；用单词 AI 命中最广，再靠 points 门槛筛热度
            hurl = (f"https://hn.algolia.com/api/v1/search_by_date?tags=story&query=AI"
                    f"&numericFilters=created_at_i%3E{ts}&hitsPerPage=80")
            data = json.loads(http_get(hurl).decode("utf-8", "replace"))
            for h in data.get("hits", []):
                if h.get("points", 0) < HN_MIN_POINTS:   # 热度门槛
                    continue
                ts2 = h.get("created_at_i")
                dt = datetime.fromtimestamp(ts2, tz=timezone.utc) if ts2 else None
                if not dt or dt < cutoff:
                    continue
                title = h.get("title") or h.get("story_title") or ""
                if not title:
                    continue
                link = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
                items.append({
                    "title": title, "url": link, "source": name, "source_tier": tier,
                    "published": dt.isoformat(), "summary": "",
                    "hn_points": h.get("points", 0), "hn_comments": h.get("num_comments", 0),
                })
        else:
            txt = http_get(url).decode("utf-8", "replace")
            for (title, link, ds, summ) in parse_xml_items(txt):
                if typ == "gnews":
                    if title.lower() in ("google news", "google 新闻"):
                        continue
                    # GNews 标题尾部 " - 媒体名"，拆出真实媒体名
                    media = ""
                    if " - " in title:
                        parts = title.rsplit(" - ", 1)
                        title, media = parts[0].strip(), parts[1].strip()
                    src_label = f"{name}/{media}" if media else name
                else:
                    src_label = name
                dt = parse_date(ds)
                if dt and dt < cutoff:
                    continue
                if not title:
                    continue
                if name in NEED_AI_FILTER and not AI_KW.search(title + " " + summ):
                    continue   # 泛科技源剔除非 AI 条目
                items.append({
                    "title": title, "url": link, "source": src_label, "source_tier": tier,
                    "published": dt.isoformat() if dt else "", "summary": summ[:600],
                    "hn_points": 0, "hn_comments": 0,
                })
        # 每源上限：按时间新→旧取前 N，把候选规模压下来
        items.sort(key=lambda x: x.get("published", ""), reverse=True)
        items = items[:PER_SOURCE_CAP.get(name, DEFAULT_CAP)]
        return (name, items, None)
    except Exception as e:
        return (name, [], str(e)[:120])


def norm_title(t):
    t = t.lower()
    t = re.sub(r"[^\w一-鿿]+", "", t)   # 去标点空格，保留中英文字
    return t


def dedupe(items):
    """跨源去重：URL 完全相同 或 标题相似度>0.82 合并；记录 sources 列表与命中源数。"""
    groups = []
    for it in items:
        nt = norm_title(it["title"])
        placed = False
        for g in groups:
            same_url = it["url"] and it["url"] == g["url"]
            sim = SequenceMatcher(None, nt, g["_nt"]).ratio()
            if same_url or sim > 0.82:
                g["sources"].append(it["source"])
                g["source_tiers"].append(it["source_tier"])
                g["hn_points"] = max(g["hn_points"], it.get("hn_points", 0))
                g["hn_comments"] = max(g["hn_comments"], it.get("hn_comments", 0))
                if len(it.get("summary", "")) > len(g.get("summary", "")):
                    g["summary"] = it["summary"]
                placed = True
                break
        if not placed:
            g = dict(it)
            g["_nt"] = nt
            g["sources"] = [it["source"]]
            g["source_tiers"] = [it["source_tier"]]
            groups.append(g)
    for g in groups:
        g.pop("_nt", None)
        g["source_count"] = len(set(g["sources"]))
        g["best_tier"] = min(g["source_tiers"])
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=36)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    all_items, errors = [], []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = [ex.submit(fetch, n, t, u, tier, cutoff) for (n, t, u, tier) in SOURCES]
        for f in as_completed(futs):
            name, items, err = f.result()
            if err:
                errors.append((name, err))
            all_items.extend(items)
            print(f"  [{name}] {len(items)} 条" + (f"  ×{err}" if err else ""))

    merged = dedupe(all_items)

    # 排序：多源 → 高档 → 新 在前（仅排序提示，真正打分/跨语言聚类在 agent 层）
    def sortkey(g):
        try:
            t = datetime.fromisoformat(g["published"]).timestamp() if g.get("published") else 0
        except Exception:
            t = 0
        return (-g["source_count"], g["best_tier"], -t)
    merged.sort(key=sortkey)

    date_str = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), f"data_news_{date_str}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(),
                   "window_hours": args.hours, "raw_count": len(all_items),
                   "merged_count": len(merged), "errors": errors,
                   "items": merged}, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print(f"原始 {len(all_items)} 条 → 去重后 {len(merged)} 条  (窗口 {args.hours}h)")
    print(f"失败源: {[e[0] for e in errors] or '无'}")
    print(f"输出: {out}")
    print("=" * 70)
    print("\n多源命中 ≥2 的条目（最可能是重大事件）:")
    for g in [x for x in merged if x["source_count"] >= 2][:15]:
        print(f"  [{g['source_count']}源·tier{g['best_tier']}] {g['title'][:60]}")
        print(f"       来源: {', '.join(sorted(set(g['sources'])))[:90]}")


if __name__ == "__main__":
    main()
