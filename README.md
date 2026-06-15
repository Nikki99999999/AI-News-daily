# AI News Daily

AI 行业重大新闻日报的抓取与编排仓库。复用 `follow-builders` 模式:GitHub Actions 定时抓取并把结果 commit 进仓库,claude.ai 云端 routine 只读 raw 数据做多 agent 编排,最后邮件投递。

## 定位

聚焦 AI 行业**重大事件**(模型/产品发布、融资并购、监管政策、重要开源)。与「AI Builders 简报」互补:那份讲圈内构建者动态,这份讲行业大事。本仓库**不含 X 板块**(X 由 AI Builders 覆盖,日后两份合并)。

重大性判断引入「LLM 三大限制地图」做归类与加权:每条新闻归到 A(Context 有效性)/ B(Feedback 闭环)/ C(反均值)之一或标为外围配套,命中三类的加打分权重。

## 架构

```
① GitHub Actions（每天 UTC 23:00 = 上海 07:00,网络无限制）
   └ fetch_news.py 抓 21 源 → 跨源机械去重/限量 → 写 data/latest.json → commit
        │  raw.githubusercontent.com/Nikki99999999/AI-News-daily/main/data/latest.json
        ▼
② claude.ai 云端 routine（每天上海 08:00,白名单仅 raw.github + api.resend）
   主 Opus:拉 latest.json
     ├ 4 个 Sonnet 采分 subagent（按源档,定义见 .claude/agents/）
     ├ 汇总:跨档语义聚类 + 三限制加权 + 今日地图总结 + 成稿
     ├ 2 个 Sonnet 复核 subagent（事实核验 + 标准符合）
     └ 定稿 → 科技感 PDF → Resend 发邮箱
```

抓取的网络脏活在 Actions 里干(不受云端白名单限制),云端只做认知编排。

## 目录

| 路径 | 用途 |
|---|---|
| `fetch_news.py` | 抓取层(零依赖,仅 stdlib),21 源并行抓取 + 去重 + 限量 |
| `.github/workflows/fetch.yml` | Actions 定时抓取并 commit `data/latest.json` |
| `data/latest.json` | 最新一期候选(由 Actions 维护,云端 routine 读取) |
| `.claude/agents/` | 6 个 subagent 定义(4 采分 + 2 复核),随云端 clone 带入 routine |

## 本地运行

```bash
python fetch_news.py --hours 36              # 抓最近 36h,输出 data_news_<date>.json
python fetch_news.py --hours 36 --out data/latest.json
```

## 说明

- 本仓库公开,**不含任何密钥**。Resend API key 等存放在 claude.ai routine 的私有配置里,不进仓库。
- 数据源清单与各源接入方式见 `fetch_news.py` 顶部的 `SOURCES`。
