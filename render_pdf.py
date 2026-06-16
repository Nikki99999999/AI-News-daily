# -*- coding: utf-8 -*-
"""AI 行业日报 PDF 渲染（苹果极简风：白底 / 近黑正文 / 单一蓝强调 / 细灰线 / 大留白）。
结构：刊头 + 技术演进图谱(A/B/C 三段研判) + 六部分 + 每条地图注释行。

用法:
    python render_pdf.py [digest.json] [out.pdf]
默认读 data/latest_digest.json，输出同名 .pdf。
字体自动回退: Noto Sans SC(云端 /tmp) → 微软雅黑(本地) → 黑体。
"""
import json, sys, os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, KeepTogether, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle

def _reg(name, path):
    if path.lower().endswith(".ttc"):
        pdfmetrics.registerFont(TTFont(name, path, subfontIndex=0))
    else:
        pdfmetrics.registerFont(TTFont(name, path))

REG_FONTS  = ["/tmp/NotoSansSC.ttf", "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"]
BOLD_FONTS = ["/tmp/NotoSansSC.ttf", "C:/Windows/Fonts/msyhbd.ttc"]
reg = next((f for f in REG_FONTS if os.path.exists(f)), REG_FONTS[0])
bold = next((f for f in BOLD_FONTS if os.path.exists(f)), reg)
_reg("CN", reg)
_reg("CNB", bold)

INK="#1d1d1f"; MUTED="#86868b"; LINE="#d2d2d7"; PANEL="#f5f5f7"; ACCENT="#0071e3"
W, H = A4

digest_path = sys.argv[1] if len(sys.argv) > 1 else "data/latest_digest.json"
out_path = sys.argv[2] if len(sys.argv) > 2 else digest_path.rsplit(".", 1)[0] + ".pdf"
DATA = json.load(open(digest_path, encoding="utf-8"))

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
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

TAGCN = {"A": "A·上下文", "B": "B·闭环", "C": "C·反均值", "配套": "配套"}
story = []

story.append(Paragraph("AI 行业日报", H1))
story.append(Paragraph(DATA.get("date_str", "") + "　　行业重大事件 · 三限制研判", SUB))
story.append(Spacer(1, 10))
story.append(HRFlowable(width="100%", thickness=0.8, color=HexColor(LINE), spaceAfter=14))

# 技术演进图谱（结论框）
ev = DATA.get("evolution", {}); c = ev.get("counts", {})
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

for title, items in DATA.get("sections", []):
    if not items:
        continue
    story.append(Paragraph('<font color="%s">▎</font> %s' % (ACCENT, esc(title)), H2))
    for it in items:
        mc = it.get("map_class", "")
        if not mc and not it.get("url"):   # 总结/展望类
            story.append(Paragraph(esc(it["title_cn"]), SUMT))
            story.append(Paragraph(esc(it.get("summary_cn", "")), BODY))
            continue
        tag = TAGCN.get(mc, "配套")
        tagcolor = MUTED if mc == "配套" else ACCENT
        sc = it.get("score", "")
        head = esc(it["title_cn"])
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

doc = SimpleDocTemplate(out_path, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=22*mm, bottomMargin=22*mm)
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("PDF OK ->", out_path)
