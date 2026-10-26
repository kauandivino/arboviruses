"""Leitura local de PDF com texto, posições e ângulos dos caracteres."""
import math
import re
import pypdfium2 as pdfium


def lines_and_words(page):
    textpage = page.get_textpage()
    lines, current = [], []
    def flush():
        nonlocal current
        if current:
            text = ''.join(c['text'] for c in current).strip()
            if text:
                visible = [c for c in current if c['text'].strip()]
                lines.append(dict(text=text, chars=current, bbox=bounds(visible),
                                  rotated=sum(abs(math.sin(c['angle'])) > .15 for c in visible) / len(visible) > .7))
            current = []
    try:
        for i in range(textpage.count_chars()):
            char = chr(pdfium.raw.FPDFText_GetUnicode(textpage, i))
            if char in '\r\n':
                flush()
            else:
                current.append(dict(text=char, bbox=list(textpage.get_charbox(i)),
                                    angle=pdfium.raw.FPDFText_GetCharAngle(textpage, i)))
        flush()
    finally:
        textpage.close()
    words = []
    for line in lines:
        chars = line['chars']
        raw = ''.join(c['text'] for c in chars)
        for match in re.finditer(r'\S+', raw):
            words.append(dict(text=match[0], bbox=bounds(chars[match.start():match.end()]), rotated=line['rotated']))
    return lines, words


def bounds(chars):
    boxes = [c['bbox'] for c in chars]
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def chart_values(page):
    """Lê números impressos alinhados a rótulos inclinados; não estima alturas."""
    lines, words = lines_and_words(page)
    labels = [line for line in lines if line['rotated'] and re.search(r'[A-Za-zÀ-ÿ]{2}', line['text'])]
    if not 3 <= len(labels) <= 50:
        raise ValueError(f'Quantidade de rótulos inclinados não reconhecida: {len(labels)}')
    title_lines = [line for line in lines if 'bairro' in line['text'].lower() and not line['rotated']]
    if not title_lines:
        raise ValueError('Título territorial não localizado')
    upper = max(line['bbox'][1] for line in title_lines) - 22
    lower = max(line['bbox'][3] for line in labels) + 2
    positions = sorted(line['bbox'][2] for line in labels)
    gap = min(b-a for a,b in zip(positions, positions[1:]))
    if gap < 10:
        raise ValueError('Rótulos sobrepostos ou múltiplos gráficos')
    tolerance = min(9., gap * .22)
    numbers = [w for w in words if not w['rotated'] and re.fullmatch(r'\d+(?:\.\d{3})*', w['text'])
               and lower < (w['bbox'][1]+w['bbox'][3])/2 < upper]
    result, used = [], set()
    for label in labels:
        # O final do nome inclinado fica junto ao centro da barra.
        x = label['bbox'][2] - 2
        matches = [(i,n) for i,n in enumerate(numbers) if abs((n['bbox'][0]+n['bbox'][2])/2-x) <= tolerance]
        if len(matches) != 1 or matches[0][0] in used:
            raise ValueError(f'Associação não unívoca entre bairro e número: {label["text"]} ({len(matches)})')
        index, number = matches[0]; used.add(index)
        result.append(dict(bairro=label['text'], valor_original=number['text'],
                           valor=int(number['text'].replace('.', '')), bbox_bairro=label['bbox'],
                           bbox_valor=number['bbox']))
    # Números acima de barras de mesma série devem acompanhar a escala vertical.
    xs = [r['valor'] for r in result]
    ys = [(r['bbox_valor'][1]+r['bbox_valor'][3])/2 for r in result]
    mx, my = sum(xs)/len(xs), sum(ys)/len(ys)
    denominator = sum((x-mx)**2 for x in xs)
    if denominator:
        slope = sum((x-mx)*(y-my) for x,y in zip(xs,ys))/denominator
        error = max(abs(y-(my+slope*(x-mx))) for x,y in zip(xs,ys))
        if slope <= 0 or error > 3:
            raise ValueError(f'Números incompatíveis com escala vertical única (erro {error:.2f})')
    return sorted(result, key=lambda r:r['bbox_valor'][0])
