#!/usr/bin/env python3
"""IKEA-like visual PDF layout from *real, supplied* step PNGs.
Images must originate from actual CAD/manual review; missing images remain placeholders.
This is a DRAFT renderer, NOT a CAD path validation engine.
Optional dependency: pip install reportlab
"""
import argparse
import math
import os
import pathlib
import sys

from assembly_cli import read_json, evaluate

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A3, A4, landscape, portrait
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except ImportError as e:
    raise SystemExit("缺少 ReportLab：python -m pip install reportlab") from e

def register_cjk_font():
    candidates = [os.environ.get('ASSEMBLY_PDF_FONT'),
                  r'C:\Windows\Fonts\msjh.ttc',
                  r'C:\Windows\Fonts\mingliu.ttc',
                  '/usr/share/fonts/truetype/arphic-bsmi00lp/bsmi00lp.ttf',
                  '/usr/share/fonts/truetype/arphic-bkai00mp/bkai00mp.ttf']
    for filename in candidates:
        if filename and pathlib.Path(filename).is_file():
            try:
                pdfmetrics.registerFont(TTFont('AssemblyCJK',filename,subfontIndex=0))
                return 'AssemblyCJK'
            except Exception:
                continue
    raise SystemExit('找不到可嵌入的中文字型，請指定 ASSEMBLY_PDF_FONT 為支援繁體中文的 .ttf/.ttc 字型檔路徑')

FONT = register_cjk_font()


def emit(job: pathlib.Path, require_images=False):
    plan = read_json(job / 'plan.json')
    checked = evaluate(plan)
    if checked['errors']:
        raise ValueError('組裝計畫資料不完整：' + '; '.join(checked['errors']))
    size = A3 if plan['settings'].get('paper') == 'A3' else A4
    size = landscape(size) if plan['settings'].get('orientation') == 'landscape' else portrait(size)
    w, h = size
    margin = 42
    # A4 portrait two steps per page; otherwise one generous step per page.
    n_per_page = 2 if w < h and plan['settings'].get('layout') == 'adaptive' else 1
    slots = []
    for step in plan['steps']:
        image = job / 'visuals' / f'{step["id"]}.png'
        if require_images and not image.is_file():
            raise ValueError(f'缺少真實 CAD 步驟圖片：{image}')
        slots.append((step, image if image.is_file() else None))
    out_dir = job / 'output'
    out_dir.mkdir(exist_ok=True)
    dest = out_dir / 'IKEA_Layout_DRAFT.pdf'
    if dest.exists():
        raise ValueError('目標 PDF 已存在。為避免覆寫請先改用新 job 或備份後自行處理。')
    c = canvas.Canvas(str(dest), pagesize=size, pageCompression=1)
    c.setTitle('Assembly Instructions - DRAFT (visual layout only)')
    pagecount = math.ceil(len(slots) / n_per_page)
    for index in range(pagecount):
        start = index*n_per_page
        part = slots[start:start+n_per_page]
        c.setStrokeColorRGB(.1,.1,.1)
        c.setFillColorRGB(.08,.08,.08)
        c.setFont(FONT, 17)
        c.drawString(margin, h-margin+7, '組裝說明  |  ASSEMBLY INSTRUCTIONS')
        c.setLineWidth(1.7)
        c.line(margin,h-margin-6,w-margin,h-margin-6)
        free_top = h-margin-22
        free_bottom = margin+34
        cell_height = (free_top-free_bottom)/n_per_page
        for k, (step, source) in enumerate(part):
            top = free_top-k*cell_height
            low = top-cell_height
            c.setFillColorRGB(0,0,0)
            c.setFont(FONT,16)
            c.drawString(margin,top-25, step['id'] + '   ' + str(step.get('title',''))[:34])
            c.setFont(FONT,10)
            c.drawString(margin, low+22, '本步零件：' + ', '.join(step.get('add',[]))[:75])
            desc = str(step.get('instructions',''))[:95]
            c.drawString(margin,low+8,desc)
            imgbox = (margin+2, low+44, w-2*margin-4, cell_height-84)
            x,y,iw,ih=imgbox
            if source is not None:
                ir=ImageReader(str(source))
                pw,ph=ir.getSize()
                factor=min(iw/pw,ih/ph)
                rw,rh=pw*factor,ph*factor
                c.drawImage(ir,x+(iw-rw)/2,y+(ih-rh)/2,width=rw,height=rh,mask='auto')
                # Arrows must be explicitly approved and use normalized page-image coordinates.
                arrows = step.get('visual', {}).get('arrows', [])
                if arrows and step.get('review', {}).get('approved'):
                    c.setStrokeColorRGB(0,0,0)
                    c.setLineWidth(2.3)
                    for arrow in arrows:
                        coords=arrow.get('from',[])+arrow.get('to',[])
                        if len(coords) != 4 or any(not isinstance(v,(float,int)) or not (0 <= v <= 1) for v in coords):
                            raise ValueError(f"箭頭座標無效：{step['id']}")
                        ax=x+(iw-rw)/2+coords[0]*rw
                        ay=y+(ih-rh)/2+(1-coords[1])*rh
                        bx=x+(iw-rw)/2+coords[2]*rw
                        by=y+(ih-rh)/2+(1-coords[3])*rh
                        c.line(ax,ay,bx,by)
                        a=math.atan2(by-ay,bx-ax)
                        size=9
                        for off in (0.48,-0.48):
                            c.line(bx,by,bx-size*math.cos(a+off),by-size*math.sin(a+off))
                elif arrows:
                    raise ValueError(f'未經人工核准的箭頭不可輸出：{step["id"]}')
            else:
                c.setStrokeColorRGB(.65,.65,.65)
                c.rect(x,y,iw,ih)
                c.setFillColorRGB(.46,.46,.46)
                c.setFont(FONT,12)
                c.drawCentredString(x+iw/2,y+ih/2,'尚未提供真實 CAD 視圖圖片')
            if k < n_per_page-1:
                c.setStrokeColorRGB(.6,.6,.6)
                c.line(margin,low-2,w-margin,low-2)
        c.setFillColorRGB(.56,.1,.1)
        c.setFont(FONT,11)
        c.drawString(margin, margin-4,'DRAFT — 圖面與裝配順序尚須人工審核')
        c.setFillColorRGB(.1,.1,.1)
        c.drawRightString(w-margin,margin-4,f'{index+1} / {pagecount}')
        c.showPage()
    c.save()
    return dest


def main():
    parser = argparse.ArgumentParser(description='Visual IKEA-like PDF (draft) from verified step images')
    parser.add_argument('--job', required=True)
    parser.add_argument('--require-images', action='store_true')
    args = parser.parse_args()
    try:
        print('產生視覺版面草稿：',emit(pathlib.Path(args.job).resolve(),args.require_images))
    except (ValueError,OSError) as e:
        print('ERROR:',e,file=sys.stderr)
        return 2
    return 0

if __name__=='__main__':
    raise SystemExit(main())
