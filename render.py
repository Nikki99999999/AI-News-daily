# -*- coding: utf-8 -*-
"""AI 行业日报统一渲染器（单一设计系统 → 邮件 HTML + PDF 一致）。

同一份 digest.json 同时驱动两种产物，共用一套设计令牌（颜色 / 字体 / 版式 / 结构），
邮件正文不再每天即兴拼裸 HTML，保证邮件与 PDF 视觉一致：
  · 邮件 HTML：table 布局 + 全内联样式，QQ 邮箱 / Gmail 安全（不依赖 <style>/flex/grid/外链 CSS）
  · PDF：reportlab 苹果极简风（白底 / 近黑正文 / 单一蓝强调 / 细灰线 / 大留白）

用法:
    python render.py [digest.json] [out_basename]
默认读 data/latest_digest.json，写出同目录的 .pdf 与 .html（邮件正文）。
也可被 import：render_email_html(digest)->str / render_pdf(digest, out_pdf)。
字体回退: Noto Sans SC(/tmp) → 微软雅黑(本地) → 黑体。
"""
import json, sys, os

# ---------- 共享设计令牌（苹果官网色板，邮件与 PDF 共用） ----------
INK    = "#1d1d1f"   # 正文近黑
MUTED  = "#86868b"   # 次要文字
LINE   = "#d2d2d7"   # 细分割线
PANEL  = "#f5f5f7"   # 浅灰卡片底
ACCENT = "#0071e3"   # 单一强调蓝
PAGE   = "#f5f5f7"   # 邮件外层页底
WHITE  = "#ffffff"
FONT_STACK = ('-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",'
              '"Helvetica Neue",Arial,sans-serif')

TAGCN = {"A": "A·上下文", "B": "B·闭环", "C": "C·反均值", "配套": "配套"}


# ========================================================================
#  邮件 HTML 渲染（email-client 安全：table + 内联样式）
# ========================================================================
def _esc_html(t):
    return (str(t) if t is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_email_html(d):
    date_str = d.get("date_str", "")
    ev = d.get("evolution", {}) or {}
    c = ev.get("counts", {}) or {}

    P = []  # HTML 片段累加
    A = P.append

    # —— 文档骨架 + 外层页底 ——
    A('<!DOCTYPE html><html><head><meta charset="utf-8">'
      '<meta name="viewport" content="width=device-width,initial-scale=1">'
      '<meta name="x-apple-disable-message-reformatting"></head>')
    A('<body style="margin:0;padding:0;background:%s;">' % PAGE)
    A('<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0" '
      'style="background:%s;width:100%%;">' % PAGE)
    A('<tr><td align="center" style="padding:24px 12px;">')
    # —— 内容卡 ——
    A('<table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" '
      'style="width:640px;max-width:640px;background:%s;border-radius:14px;overflow:hidden;'
      'font-family:%s;color:%s;">' % (WHITE, FONT_STACK, INK))

    # —— 刊头 ——
    A('<tr><td style="padding:40px 36px 14px 36px;">')
    A('<div style="font-size:30px;font-weight:700;letter-spacing:-0.5px;line-height:1.2;color:%s;">'
      'AI 行业日报</div>' % INK)
    A('<div style="font-size:14px;color:%s;line-height:1.5;padding-top:8px;">%s</div>'
      % (MUTED, _esc_html(date_str + "　行业重大事件 · 三限制研判")))
    A('</td></tr>')
    A('<tr><td style="padding:0 36px;"><div style="border-top:1px solid %s;line-height:1px;'
      'font-size:1px;">&nbsp;</div></td></tr>' % LINE)

    # —— 今日技术演进图谱（强调色左条卡片）——
    A('<tr><td style="padding:22px 36px 4px 36px;">')
    A('<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0" '
      'style="background:%s;border-radius:12px;">' % PANEL)
    A('<tr>')
    A('<td width="4" style="width:4px;background:%s;border-radius:12px 0 0 12px;"></td>' % ACCENT)
    A('<td style="padding:18px 20px;">')
    A('<div style="font-size:15px;font-weight:700;color:%s;">今日技术演进图谱</div>' % INK)
    cnt = "今日命中　A·上下文 %d　·　B·闭环 %d　·　C·反均值 %d　·　配套 %d" % (
        c.get("A", 0), c.get("B", 0), c.get("C", 0), c.get("配套", 0))
    A('<div style="font-size:12px;color:%s;padding:4px 0 8px 0;">%s</div>' % (MUTED, _esc_html(cnt)))
    for k, label in [("a", "A · 上下文有效性"), ("b", "B · 反馈闭环"), ("c", "C · 反均值")]:
        if ev.get(k):
            A('<div style="font-size:13px;color:%s;line-height:1.65;padding-bottom:5px;">'
              '<span style="color:%s;font-weight:700;">%s　</span>%s</div>'
              % (INK, ACCENT, label, _esc_html(ev[k])))
    if ev.get("verdict"):
        A('<div style="border-top:1px solid %s;margin:8px 0 0 0;padding-top:8px;'
          'font-size:13px;color:%s;line-height:1.65;">'
          '<span style="font-weight:700;">研判　</span>%s</div>' % (LINE, INK, _esc_html(ev["verdict"])))
    A('</td></tr></table>')
    A('</td></tr>')

    # —— 六部分 ——
    for sec in d.get("sections", []) or []:
        if not sec or len(sec) < 2:
            continue
        title, items = sec[0], sec[1] or []
        if not items:
            continue
        A('<tr><td style="padding:26px 36px 2px 36px;">')
        A('<div style="font-size:17px;font-weight:700;color:%s;">'
          '<span style="color:%s;">▎</span> %s</div>' % (INK, ACCENT, _esc_html(title)))
        A('</td></tr>')
        for it in items:
            mc = it.get("map_class", "")
            A('<tr><td style="padding:8px 36px 4px 36px;">')
            # 标题（+ 评分）
            head = '<span style="font-size:15px;font-weight:700;color:%s;line-height:1.45;">%s</span>' % (
                INK, _esc_html(it.get("title_cn", "")))
            sc = it.get("score", "")
            if sc not in ("", None):
                head += '<span style="font-size:11px;color:%s;font-weight:400;">　评分 %s</span>' % (
                    MUTED, _esc_html(sc))
            A('<div style="padding-bottom:4px;">%s</div>' % head)
            # 摘要
            if it.get("summary_cn"):
                A('<div style="font-size:14px;color:%s;line-height:1.7;padding-bottom:5px;">%s</div>'
                  % (INK, _esc_html(it["summary_cn"])))
            # 地图注释行
            if mc:
                tagcolor = MUTED if mc == "配套" else ACCENT
                note = '<span style="color:%s;">地图 · %s</span>' % (tagcolor, _esc_html(TAGCN.get(mc, "配套")))
                if it.get("advance_point"):
                    note += '<span style="color:%s;">　|　推进点：%s</span>' % (MUTED, _esc_html(it["advance_point"]))
                A('<div style="font-size:12px;line-height:1.5;padding-bottom:3px;">%s</div>' % note)
            # 来源 · 原文
            meta = []
            if it.get("sources_label"):
                meta.append('<span style="color:%s;">%s</span>' % (MUTED, _esc_html(it["sources_label"])))
            if it.get("url"):
                meta.append('<a href="%s" style="color:%s;text-decoration:none;">原文 &rsaquo;</a>'
                            % (_esc_html(it["url"]), ACCENT))
            if meta:
                A('<div style="font-size:12px;color:%s;">%s</div>'
                  % (MUTED, '　·　'.join(meta)))
            A('</td></tr>')

    # —— 页脚 ——
    A('<tr><td style="padding:28px 36px 32px 36px;border-top:1px solid %s;background:%s;">'
      '<div style="font-size:12px;color:%s;line-height:1.6;">'
      'AI 行业日报 · 由 LLM 三限制地图归类加权，经两道复核生成<br>'
      '完整排版与全部条目见随附 PDF</div></td></tr>' % (LINE, "#fafafa", MUTED))

    A('</table></td></tr></table></body></html>')
    return "".join(P)


# ========================================================================
#  PDF 渲染（reportlab，与邮件同令牌同结构）
# ========================================================================
def render_pdf(d, out_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
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

    REG_FONTS  = ["/tmp/NotoSansSC.ttf", "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"]
    BOLD_FONTS = ["/tmp/NotoSansSC.ttf", "C:/Windows/Fonts/msyhbd.ttc"]
    reg  = next((f for f in REG_FONTS if os.path.exists(f)), REG_FONTS[0])
    bold = next((f for f in BOLD_FONTS if os.path.exists(f)), reg)
    _reg("CN", reg)
    _reg("CNB", bold)

    W, H = A4
    H1   = ParagraphStyle("h1",  fontName="CNB", fontSize=27, textColor=HexColor(INK),   leading=33, spaceAfter=3)
    SUB  = ParagraphStyle("sub", fontName="CN",  fontSize=11, textColor=HexColor(MUTED), leading=16)
    EVLAB= ParagraphStyle("el",  fontName="CNB", fontSize=11, textColor=HexColor(INK),   leading=16, spaceAfter=2)
    EVCNT= ParagraphStyle("ec",  fontName="CN",  fontSize=9,  textColor=HexColor(MUTED), leading=14, spaceAfter=7)
    EVSEG= ParagraphStyle("es",  fontName="CN",  fontSize=10, textColor=HexColor(INK),   leading=16.5, spaceAfter=6)
    EVVER= ParagraphStyle("ev",  fontName="CN",  fontSize=10, textColor=HexColor(INK),   leading=16.5, spaceBefore=2)
    H2   = ParagraphStyle("h2",  fontName="CNB", fontSize=15, textColor=HexColor(INK),   leading=20, spaceBefore=22, spaceAfter=9)
    TIT  = ParagraphStyle("tit", fontName="CNB", fontSize=12, textColor=HexColor(INK),   leading=17, spaceBefore=11, spaceAfter=3)
    BODY = ParagraphStyle("bd",  fontName="CN",  fontSize=10.5, textColor=HexColor(INK), leading=17.5, spaceAfter=3)
    NOTE = ParagraphStyle("nt",  fontName="CN",  fontSize=9,  textColor=HexColor(MUTED), leading=14, spaceAfter=2, leftIndent=2)
    META = ParagraphStyle("me",  fontName="CN",  fontSize=8.5, textColor=HexColor(MUTED), leading=12, spaceAfter=2)
    SUMT = ParagraphStyle("st",  fontName="CNB", fontSize=11.5, textColor=HexColor(INK), leading=16, spaceBefore=9, spaceAfter=3)

    def esc(t):
        return (str(t) if t is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    story = []
    story.append(Paragraph("AI 行业日报", H1))
    story.append(Paragraph(d.get("date_str", "") + "　　行业重大事件 · 三限制研判", SUB))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.8, color=HexColor(LINE), spaceAfter=14))

    ev = d.get("evolution", {}) or {}; c = ev.get("counts", {}) or {}
    cnt = "今日命中　A·上下文 %d　·　B·闭环 %d　·　C·反均值 %d　·　配套 %d" % (
        c.get("A", 0), c.get("B", 0), c.get("C", 0), c.get("配套", 0))
    panel = [Paragraph("今日技术演进图谱", EVLAB), Paragraph(cnt, EVCNT)]
    for k, label in [("a", "A · 上下文有效性"), ("b", "B · 反馈闭环"), ("c", "C · 反均值")]:
        if ev.get(k):
            panel.append(Paragraph('<font color="%s"><b>%s　</b></font>%s' % (ACCENT, label, esc(ev[k])), EVSEG))
    if ev.get("verdict"):
        panel.append(HRFlowable(width="100%", thickness=0.5, color=HexColor(LINE), spaceBefore=2, spaceAfter=6))
        panel.append(Paragraph('<b>研判　</b>%s' % esc(ev["verdict"]), EVVER))
    if panel:
        tbl = Table([[panel]], colWidths=[W - 40*mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), HexColor(PANEL)),
            ("LINEBEFORE", (0,0), (0,-1), 2.5, HexColor(ACCENT)),
            ("LEFTPADDING", (0,0), (-1,-1), 18), ("RIGHTPADDING", (0,0), (-1,-1), 18),
            ("TOPPADDING", (0,0), (-1,-1), 16), ("BOTTOMPADDING", (0,0), (-1,-1), 16),
        ]))
        story.append(tbl)

    for sec in d.get("sections", []) or []:
        if not sec or len(sec) < 2:
            continue
        title, items = sec[0], sec[1] or []
        if not items:
            continue
        story.append(Paragraph('<font color="%s">▎</font> %s' % (ACCENT, esc(title)), H2))
        for it in items:
            mc = it.get("map_class", "")
            if not mc and not it.get("url"):   # 总结/展望类
                story.append(Paragraph(esc(it.get("title_cn", "")), SUMT))
                story.append(Paragraph(esc(it.get("summary_cn", "")), BODY))
                continue
            tag = TAGCN.get(mc, "配套")
            tagcolor = MUTED if mc == "配套" else ACCENT
            sc = it.get("score", "")
            head = esc(it.get("title_cn", ""))
            if sc not in ("", None):
                head += '　<font color="%s" size="8">评分 %s</font>' % (MUTED, esc(str(sc)))
            parts = [Paragraph(head, TIT), Paragraph(esc(it.get("summary_cn", "")), BODY)]
            if mc:
                note = '<font color="%s">地图 · %s</font>' % (tagcolor, esc(tag))
                if it.get("advance_point"):
                    note += '　|　推进点：%s' % esc(it["advance_point"])
                parts.append(Paragraph(note, NOTE))
            meta = []
            if it.get("sources_label"):
                meta.append(esc(it["sources_label"]))
            if it.get("url"):
                meta.append('<link href="%s"><font color="%s">原文</font></link>' % (esc(it["url"]), ACCENT))
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
                            topMargin=22*mm, bottomMargin=22*mm)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


# ========================================================================
#  CLI：一份 digest → 同时出 PDF + 邮件 HTML
# ========================================================================
if __name__ == "__main__":
    digest_path = sys.argv[1] if len(sys.argv) > 1 else "data/latest_digest.json"
    base = sys.argv[2] if len(sys.argv) > 2 else digest_path.rsplit(".", 1)[0]
    out_pdf  = base + ".pdf"
    out_html = base + ".html"
    DATA = json.load(open(digest_path, encoding="utf-8"))

    html = render_email_html(DATA)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML OK ->", out_html)

    render_pdf(DATA, out_pdf)
    print("PDF OK ->", out_pdf)
