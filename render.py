# -*- coding: utf-8 -*-
"""AI 行业日报统一渲染器（单一设计系统 → 邮件 HTML + PDF 一致）。

同一份 digest.json 同时驱动两种产物，共用一套设计令牌（颜色 / 字体 / 版式 / 结构），
邮件正文不再每天即兴拼裸 HTML，保证邮件与 PDF 视觉一致。当前主题：Emerald 祖母绿杂志
（满版祖母绿报头 + 藏青衬线大标题 + 双线装饰，正文白底藏青衬线标题配祖母绿点缀）。
  · 邮件 HTML：table 布局 + 全内联样式，QQ 邮箱 / Gmail 安全；衬线字体经 Google Fonts 渐进增强，
    被邮件客户端剥离时优雅回退系统字体，版式与配色不变。
  · PDF：reportlab，与邮件同色板同结构；标题用 Noto Serif SC 衬线，正文 Noto Sans SC。

换主题：只改 THEME 字典里的颜色令牌（已抽成单一数据源）。
用法:
    python render.py [digest.json] [out_basename]
默认读 data/latest_digest.json，写出同目录的 .pdf 与 .html（邮件正文）。
也可被 import：render_email_html(digest)->str / render_pdf(digest, out_pdf)。
字体回退: /tmp/NotoSerifSC.ttf(标题) /tmp/NotoSansSC.ttf(正文) → 微软雅黑 → 黑体。
"""
import json, sys, os

# ===================== 设计令牌（Emerald 祖母绿杂志，单一数据源） =====================
THEME = {
    "em":     "#22c38d",   # 祖母绿报头底
    "navy":   "#152a63",   # 藏青（标题主色）
    "ink":    "#19223f",   # 正文标题近藏青
    "body":   "#3a4250",   # 正文文字
    "muted":  "#8e96a3",   # 次要文字
    "line":   "#dde6e0",   # 细分割线
    "panel":  "#e9f1ec",   # 浅绿卡片底
    "green":  "#0f9a6a",   # 祖母绿强调（标签/链接/编号）
    "page":   "#e8efe9",   # 邮件外层页底
    "card":   "#fbfdfb",   # 内容卡底
    "foot":   "#f3f7f4",
}
TAGCN = {"A": "A·上下文", "B": "B·闭环", "C": "C·反均值", "配套": "配套"}
CN = ["01", "02", "03", "04", "05", "06", "07", "08"]

# 邮件字体栈（Google Fonts 渐进增强 + 系统回退）
_GFONTS = ('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&'
    'family=Noto+Serif+SC:wght@500;700;900&family=Noto+Sans+SC:wght@300;400;500;700&display=swap" rel="stylesheet">')
SERIF = '"Fraunces","Noto Serif SC",Georgia,"Songti SC",serif'
SANS  = '"Noto Sans SC","Helvetica Neue",Arial,sans-serif'


# ========================================================================
#  邮件 HTML 渲染（email-client 安全：table + 内联样式）
# ========================================================================
def _esc(t):
    return (str(t) if t is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_email_html(d):
    T = THEME
    em, navy, ink, body, muted, line, green, page, card = (
        T["em"], T["navy"], T["ink"], T["body"], T["muted"], T["line"], T["green"], T["page"], T["card"])
    P = []; A = P.append

    A('<!DOCTYPE html><html><head><meta charset="utf-8">'
      '<meta name="viewport" content="width=device-width,initial-scale=1">'
      '<meta name="x-apple-disable-message-reformatting">' + _GFONTS + '</head>')
    A('<body style="margin:0;padding:0;background:%s;">' % page)
    A('<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0" style="background:%s;width:100%%;">'
      '<tr><td align="center" style="padding:30px 14px;">' % page)
    A('<table role="presentation" width="660" cellpadding="0" cellspacing="0" border="0" '
      'style="width:660px;max-width:660px;background:%s;font-family:%s;color:%s;">' % (card, SANS, ink))

    # —— 满版祖母绿报头 ——
    A('<tr><td align="center" style="background:%s;padding:46px 44px 42px 44px;">' % em)
    A('<div style="font-family:%s;font-size:11px;letter-spacing:4px;font-weight:700;color:%s;text-transform:uppercase;">AI Industry Daily</div>' % (SANS, navy))
    A('<div style="font-family:%s;font-size:54px;font-weight:700;line-height:1.02;color:%s;padding-top:14px;">AI 行业日报</div>' % (SERIF, navy))
    A('<table role="presentation" align="center" style="margin:16px auto 0 auto;"><tr><td style="border-top:2px solid %s;border-bottom:2px solid %s;height:3px;width:120px;font-size:1px;line-height:1px;">&nbsp;</td></tr></table>' % (navy, navy))
    A('<div style="font-family:%s;font-size:12px;letter-spacing:2px;color:%s;text-transform:uppercase;padding-top:14px;">%s · 三限制研判</div>' % (SANS, navy, _esc(d.get("date_str", ""))))
    A('</td></tr>')

    # —— 今日技术演进图谱 ——
    ev = d.get("evolution", {}) or {}; c = ev.get("counts", {}) or {}
    A('<tr><td style="padding:26px 46px 6px 46px;"><table role="presentation" width="100%%" style="background:%s;border-radius:10px;"><tr><td style="padding:24px 26px;">' % T["panel"])
    A('<div style="font-family:%s;font-size:12px;letter-spacing:2px;font-weight:700;color:%s;text-transform:uppercase;padding-bottom:6px;">今日技术演进图谱</div>' % (SANS, navy))
    cnt = "A·上下文 %d　B·闭环 %d　C·反均值 %d　配套 %d" % (c.get("A", 0), c.get("B", 0), c.get("C", 0), c.get("配套", 0))
    A('<div style="font-family:%s;font-size:12px;color:%s;padding-bottom:12px;">%s</div>' % (SANS, muted, _esc(cnt)))
    for k, label in [("a", "A 上下文有效性"), ("b", "B 反馈闭环"), ("c", "C 反均值")]:
        if ev.get(k):
            A('<div style="font-size:14px;color:%s;line-height:1.75;padding-bottom:7px;"><span style="color:%s;font-weight:700;">%s　</span>%s</div>' % (ink, green, label, _esc(ev[k])))
    if ev.get("verdict"):
        A('<div style="border-top:1px solid %s;margin-top:10px;padding-top:10px;font-size:14px;color:%s;line-height:1.7;"><span style="color:%s;font-weight:700;">研判　</span>%s</div>' % (line, ink, green, _esc(ev["verdict"])))
    A('</td></tr></table></td></tr>')

    # —— 六部分 ——
    for i, sec in enumerate(d.get("sections", []) or []):
        if not sec or len(sec) < 2 or not sec[1]:
            continue
        title, items = sec[0], sec[1]
        A('<tr><td style="padding:32px 46px 4px 46px;">'
          '<div style="font-family:%s;font-size:12px;letter-spacing:2px;font-weight:700;color:%s;">%s</div>'
          '<div style="font-family:%s;font-size:23px;font-weight:700;color:%s;padding-top:4px;">%s</div>'
          '<div style="border-top:1px solid %s;margin-top:10px;font-size:1px;line-height:1px;">&nbsp;</div></td></tr>'
          % (SANS, green, CN[i] if i < len(CN) else str(i+1), SERIF, navy, _esc(title), line))
        for it in items:
            mc = it.get("map_class", "")
            A('<tr><td style="padding:14px 46px 6px 46px;">')
            head = '<span style="font-family:%s;font-size:17px;font-weight:700;color:%s;line-height:1.42;">%s</span>' % (SERIF, navy, _esc(it.get("title_cn", "")))
            sc = it.get("score", "")
            if sc not in ("", None):
                head += '<span style="font-family:%s;font-size:11px;color:%s;font-weight:400;"> 评分 %s</span>' % (SANS, muted, _esc(sc))
            A('<div style="padding-bottom:6px;">%s</div>' % head)
            if it.get("summary_cn"):
                A('<div style="font-size:14.5px;color:%s;line-height:1.82;padding-bottom:6px;">%s</div>' % (body, _esc(it["summary_cn"])))
            if mc:
                tc = muted if mc == "配套" else green
                note = '<span style="font-family:%s;font-size:11px;letter-spacing:1px;font-weight:700;color:%s;text-transform:uppercase;">%s</span>' % (SANS, tc, _esc(TAGCN.get(mc, "配套")))
                if it.get("advance_point"):
                    note += '<span style="color:%s;font-size:12.5px;">　推进点：%s</span>' % (muted, _esc(it["advance_point"]))
                A('<div style="line-height:2;padding-bottom:3px;">%s</div>' % note)
            meta = []
            if it.get("sources_label"):
                meta.append('<span style="color:%s;">%s</span>' % (muted, _esc(it["sources_label"])))
            if it.get("url"):
                meta.append('<a href="%s" style="color:%s;text-decoration:none;font-weight:700;">阅读原文 &rsaquo;</a>' % (_esc(it["url"]), green))
            if meta:
                A('<div style="font-size:12px;color:%s;">%s</div>' % (muted, '　·　'.join(meta)))
            A('</td></tr>')

    A('<tr><td style="padding:38px 46px 46px 46px;"><div style="border-top:1px solid %s;padding-top:18px;font-size:12px;color:%s;line-height:1.7;">AI 行业日报 · 由 LLM 三限制地图归类加权，经两道复核生成<br>完整排版与全部条目见随附 PDF</div></td></tr>' % (line, muted))
    A('</table></td></tr></table></body></html>')
    return "".join(P)


# ========================================================================
#  PDF 渲染（reportlab，与邮件同色板同结构；Emerald 祖母绿杂志）
# ========================================================================
def render_pdf(d, out_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_CENTER
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
                                    KeepTogether, Table, TableStyle)
    from reportlab.lib.styles import ParagraphStyle

    def _reg(name, path):
        if path.lower().endswith(".ttc"):
            pdfmetrics.registerFont(TTFont(name, path, subfontIndex=0))
        else:
            pdfmetrics.registerFont(TTFont(name, path))

    SANS_FONTS  = ["/tmp/NotoSansSC.ttf", "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"]
    SERIF_FONTS = ["/tmp/NotoSerifSC.ttf", "C:/Windows/Fonts/simsun.ttc", "C:/Windows/Fonts/msyh.ttc"]
    sans  = next((f for f in SANS_FONTS if os.path.exists(f)), SANS_FONTS[0])
    serif = next((f for f in SERIF_FONTS if os.path.exists(f)), sans)   # 缺衬线则回退正文字体
    _reg("CN", sans)
    _reg("CNB", next((f for f in ["/tmp/NotoSansSC.ttf", "C:/Windows/Fonts/msyhbd.ttc"] if os.path.exists(f)), sans))
    _reg("CNS", serif)

    T = THEME
    EM, NAVY, INK, BODY, MUTED, LINE, GREEN, PANEL = (
        T["em"], T["navy"], T["ink"], T["body"], T["muted"], T["line"], T["green"], T["panel"])
    W, H = A4
    FRAME = W - 40*mm

    def esc(t):
        return (str(t) if t is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # —— 报头（祖母绿块，居中藏青衬线大标题 + 双线）——
    M_OVER = ParagraphStyle("mo", fontName="CN",  fontSize=9.5, textColor=HexColor(NAVY), leading=14, alignment=TA_CENTER, spaceAfter=8)
    M_TIT  = ParagraphStyle("mt", fontName="CNS", fontSize=34, textColor=HexColor(NAVY), leading=40, alignment=TA_CENTER)
    M_SUB  = ParagraphStyle("ms", fontName="CN",  fontSize=10, textColor=HexColor(NAVY), leading=15, alignment=TA_CENTER, spaceBefore=8)
    band = [Paragraph("AI INDUSTRY DAILY", M_OVER),
            Paragraph("AI 行业日报", M_TIT),
            HRFlowable(width=120, thickness=2, color=HexColor(NAVY), spaceBefore=10, spaceAfter=2, hAlign="CENTER"),
            HRFlowable(width=120, thickness=2, color=HexColor(NAVY), spaceAfter=2, hAlign="CENTER"),
            Paragraph(esc(d.get("date_str", "")) + " · 三限制研判", M_SUB)]
    head = Table([[band]], colWidths=[FRAME])
    head.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), HexColor(EM)),
        ("LEFTPADDING", (0,0), (-1,-1), 18), ("RIGHTPADDING", (0,0), (-1,-1), 18),
        ("TOPPADDING", (0,0), (-1,-1), 26), ("BOTTOMPADDING", (0,0), (-1,-1), 26),
    ]))

    EVLAB= ParagraphStyle("el",  fontName="CNB", fontSize=10.5, textColor=HexColor(NAVY), leading=15, spaceAfter=3)
    EVCNT= ParagraphStyle("ec",  fontName="CN",  fontSize=9,  textColor=HexColor(MUTED), leading=14, spaceAfter=7)
    EVSEG= ParagraphStyle("es",  fontName="CN",  fontSize=10, textColor=HexColor(INK),   leading=16.5, spaceAfter=6)
    EVVER= ParagraphStyle("ev",  fontName="CN",  fontSize=10, textColor=HexColor(INK),   leading=16.5, spaceBefore=2)
    SECN = ParagraphStyle("sn",  fontName="CNB", fontSize=10, textColor=HexColor(GREEN), leading=14, spaceBefore=20, spaceAfter=2)
    H2   = ParagraphStyle("h2",  fontName="CNS", fontSize=17, textColor=HexColor(NAVY),  leading=22, spaceAfter=6)
    TIT  = ParagraphStyle("tit", fontName="CNS", fontSize=12.5, textColor=HexColor(NAVY), leading=17, spaceBefore=10, spaceAfter=3)
    BODYS= ParagraphStyle("bd",  fontName="CN",  fontSize=10.5, textColor=HexColor(BODY), leading=17.5, spaceAfter=3)
    NOTE = ParagraphStyle("nt",  fontName="CN",  fontSize=9,  textColor=HexColor(MUTED), leading=14, spaceAfter=2)
    META = ParagraphStyle("me",  fontName="CN",  fontSize=8.5, textColor=HexColor(MUTED), leading=12, spaceAfter=2)
    SUMT = ParagraphStyle("st",  fontName="CNS", fontSize=12, textColor=HexColor(NAVY),  leading=16, spaceBefore=9, spaceAfter=3)

    story = [head, Spacer(1, 16)]

    ev = d.get("evolution", {}) or {}; c = ev.get("counts", {}) or {}
    cnt = "今日命中　A·上下文 %d　·　B·闭环 %d　·　C·反均值 %d　·　配套 %d" % (
        c.get("A", 0), c.get("B", 0), c.get("C", 0), c.get("配套", 0))
    panel = [Paragraph("今日技术演进图谱", EVLAB), Paragraph(cnt, EVCNT)]
    for k, label in [("a", "A · 上下文有效性"), ("b", "B · 反馈闭环"), ("c", "C · 反均值")]:
        if ev.get(k):
            panel.append(Paragraph('<font color="%s"><b>%s　</b></font>%s' % (GREEN, label, esc(ev[k])), EVSEG))
    if ev.get("verdict"):
        panel.append(HRFlowable(width="100%", thickness=0.5, color=HexColor(LINE), spaceBefore=2, spaceAfter=6))
        panel.append(Paragraph('<font color="%s"><b>研判　</b></font>%s' % (GREEN, esc(ev["verdict"])), EVVER))
    tbl = Table([[panel]], colWidths=[FRAME])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), HexColor(PANEL)),
        ("LEFTPADDING", (0,0), (-1,-1), 18), ("RIGHTPADDING", (0,0), (-1,-1), 18),
        ("TOPPADDING", (0,0), (-1,-1), 16), ("BOTTOMPADDING", (0,0), (-1,-1), 16),
    ]))
    story.append(tbl)

    for i, sec in enumerate(d.get("sections", []) or []):
        if not sec or len(sec) < 2 or not sec[1]:
            continue
        title, items = sec[0], sec[1]
        story.append(Paragraph(CN[i] if i < len(CN) else str(i+1), SECN))
        story.append(Paragraph(esc(title), H2))
        story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor(LINE), spaceAfter=4))
        for it in items:
            mc = it.get("map_class", "")
            if not mc and not it.get("url"):   # 总结/展望类
                story.append(Paragraph(esc(it.get("title_cn", "")), SUMT))
                story.append(Paragraph(esc(it.get("summary_cn", "")), BODYS))
                continue
            tag = TAGCN.get(mc, "配套")
            tagcolor = MUTED if mc == "配套" else GREEN
            sc = it.get("score", "")
            head_t = esc(it.get("title_cn", ""))
            if sc not in ("", None):
                head_t += '　<font color="%s" size="8">评分 %s</font>' % (MUTED, esc(str(sc)))
            parts = [Paragraph(head_t, TIT), Paragraph(esc(it.get("summary_cn", "")), BODYS)]
            if mc:
                note = '<font color="%s"><b>%s</b></font>' % (tagcolor, esc(tag))
                if it.get("advance_point"):
                    note += '　|　推进点：%s' % esc(it["advance_point"])
                parts.append(Paragraph(note, NOTE))
            meta = []
            if it.get("sources_label"):
                meta.append(esc(it["sources_label"]))
            if it.get("url"):
                meta.append('<link href="%s"><font color="%s">阅读原文</font></link>' % (esc(it["url"]), GREEN))
            if meta:
                parts.append(Paragraph("　·　".join(meta), META))
            story.append(KeepTogether(parts))
            story.append(Spacer(1, 7))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(HexColor(LINE)); canvas.setLineWidth(0.5)
        canvas.line(20*mm, 15*mm, W - 20*mm, 15*mm)
        canvas.setFont("CN", 8); canvas.setFillColor(HexColor(MUTED))
        canvas.drawString(20*mm, 11*mm, "AI 行业日报")
        canvas.drawRightString(W - 20*mm, 11*mm, "第 %d 页" % doc.page)
        canvas.restoreState()

    doc = SimpleDocTemplate(out_path, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=18*mm, bottomMargin=22*mm)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


# ========================================================================
#  CLI：一份 digest → 同时出 PDF + 邮件 HTML
# ========================================================================
if __name__ == "__main__":
    digest_path = sys.argv[1] if len(sys.argv) > 1 else "data/latest_digest.json"
    base = sys.argv[2] if len(sys.argv) > 2 else digest_path.rsplit(".", 1)[0]
    out_pdf  = base + ".pdf"
    out_html = base + ".html"

    # fail-closed 闸门（2026-07-02 审计）：成稿结构不达标不渲染不发信。
    # 设 SKIP_DIGEST_VALIDATE=1 可临时跳过（仅供排障，正常路径不设）。
    if os.environ.get("SKIP_DIGEST_VALIDATE") != "1":
        try:
            from validate_digest import validate
            _fails = validate(digest_path, mode="news")
        except Exception as _e:
            _fails = [f"validate_digest 无法执行: {_e}"]
        if _fails:
            print(f"VALIDATE FAIL（{len(_fails)} 项），拒绝渲染:", file=sys.stderr)
            for _f in _fails:
                print(f"  - {_f}", file=sys.stderr)
            sys.exit(1)
        print(f"VALIDATE PASS: 成稿结构达标（{len(_fails)==0}）")

    DATA = json.load(open(digest_path, encoding="utf-8"))

    with open(out_html, "w", encoding="utf-8") as f:
        f.write(render_email_html(DATA))
    print("HTML OK ->", out_html)

    render_pdf(DATA, out_pdf)
    print("PDF OK ->", out_pdf)
