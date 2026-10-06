# Baut Timing, Sprachspur, Untertitel (SRT) und die HyperFrames-Komposition (index.html).
import json, os, re, subprocess, html

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

LEAD, GAP, TAIL = 0.5, 0.55, 0.9
FIXED = {'Zwischenbild': 4.0, '6.3': 7.0}
MIN_END = 28.0  # Schlusskarte

scenes = json.load(open('scenes.json', encoding='utf-8'))
for si, s in enumerate(scenes): s['aidx'] = si
# Kurzversion (ca. 3 Min.): nutzt nur bestehende Aufnahmen, keine neue Vertonung
SHORT = os.environ.get('SHORT') == '1'
KEEP = ['1.1', '1.2', '1.3', '1.4', '2.1', '2.2', '2.4', '3.1', '5.2', '6.1', '7.1']
if SHORT: scenes = [s for s in scenes if s['id'] in KEEP]
SUF = '_Kurzversion' if SHORT else ''

def dur(path):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]).decode())

# ---------- Timing ----------
EMAIL_SPOKEN = ['sophie', 'at', 'hundertmark', 'punkt', 'c', 'h']

def words_from(js, offset):
    al = js['alignment']
    chars, st, en = al['characters'], al['character_start_times_seconds'], al['character_end_times_seconds']
    out, cur = [], None
    for c, s, e in zip(chars, st, en):
        if c.isspace():
            if cur: out.append(cur); cur = None
            continue
        if cur is None: cur = {'w': '', 's': s + offset, 'e': e + offset}
        cur['w'] += c; cur['e'] = e + offset
    if cur: out.append(cur)
    # E-Mail im Untertitel wieder als Adresse zeigen
    i = 0
    while i <= len(out) - 6:
        if [re.sub(r'\W', '', x['w']).lower() for x in out[i:i + 6]] == EMAIL_SPOKEN:
            out[i:i + 6] = [{'w': 'sophie@hundertmark.ch', 's': out[i]['s'], 'e': out[i + 5]['e']}]
        i += 1
    return out

t = 0.0
segments = []  # (start, file) für die Sprachspur
sc_idx = 0
for si, s in enumerate(scenes):
    s['idx'] = si
    s['start'] = t
    s['words'] = []
    if s['id'] in FIXED:
        s['dur'] = FIXED[s['id']]
        t += s['dur']; continue
    c = t + LEAD
    first = True
    for pi, p in enumerate(s['parts']):
        if 'pause' in p:
            p['at'] = c; c += p['pause']; continue
        if not first: c += GAP
        first = False
        f = f'audio/s{s["aidx"]:02d}_p{pi}.mp3'
        js = json.load(open(f'audio/s{s["aidx"]:02d}_p{pi}.json', encoding='utf-8'))
        segments.append((c, f))
        s['words'] += words_from(js, c)
        c += dur(f)
    end = c + TAIL
    if s['id'] == '7.1': end = max(end, t + MIN_END)
    s['dur'] = round(end - t, 3)
    t = s['start'] + s['dur']
TOTAL = round(t, 3)

# ---------- Sprachspur ----------
inputs, filt = [], []
for i, (st, f) in enumerate(segments):
    inputs += ['-i', f]
    ms = int(round(st * 1000))
    filt.append(f'[{i}:a]aresample=44100,aformat=channel_layouts=mono,adelay={ms}|{ms}[a{i}]')
filt.append(''.join(f'[a{i}]' for i in range(len(segments))) + f'amix=inputs={len(segments)}:normalize=0,apad,atrim=0:{TOTAL}[out]')
subprocess.check_call(['ffmpeg', '-y', '-v', 'error', *inputs, '-filter_complex', ';'.join(filt), '-map', '[out]', '-ar', '44100', '-ac', '2', f'narration{SUF}.wav'])

# ---------- Untertitel ----------
MAXC = 84
cues = []
for s in scenes:
    cur = []
    for w in s['words']:
        txt = ' '.join(x['w'] for x in cur + [w])
        if cur and len(txt) > MAXC:
            cues.append(cur); cur = []
        cur.append(w)
        joined = ' '.join(x['w'] for x in cur)
        if re.search(r'[.?!:]$', w['w']) and len(joined) >= 38:
            cues.append(cur); cur = []
    if cur: cues.append(cur)
for i, c in enumerate(cues):
    c_start = c[0]['s'] - 0.05
    nxt = cues[i + 1][0]['s'] - 0.05 if i + 1 < len(cues) else TOTAL
    c_end = min(c[-1]['e'] + 0.6, nxt)
    cues[i] = {'words': c, 's': max(0, c_start), 'e': c_end}

def srt_t(x):
    ms = int(round(x * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); sec, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{sec:02d},{ms:03d}'
with open(f'KI_nutzen_selber_denken_Sophie_Hundertmark{SUF}.srt', 'w', encoding='utf-8') as f:
    for i, c in enumerate(cues, 1):
        f.write(f"{i}\n{srt_t(c['s'])} --> {srt_t(c['e'])}\n{' '.join(w['w'] for w in c['words'])}\n\n")

json.dump({'total': TOTAL, 'scenes': [{k: s[k] for k in ('id', 'title', 'start', 'dur')} for s in scenes]},
          open(f'timing{SUF}.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# ---------- Szenen ----------
E = html.escape
anims = []  # (selector, kind, abs_time, extra)

def norm(x): return re.sub(r'[^\wäöüÄÖÜß]', '', x).lower()

class Sc:
    def __init__(self, s):
        self.s = s; self.p = f"s{s['idx']}"
    def id(self, n): return f'{self.p}-{n}'
    def kw(self, word, n=1, dflt=0.6):
        k = 0
        for w in self.s['words']:
            if any(norm(part).startswith(norm(word)) for part in [w['w']] + w['w'].split('-')):
                k += 1
                if k == n: return w['s'] - self.s['start']
        raise SystemExit(f"Stichwort '{word}' ({n}) nicht in Szene {self.s['id']}")
    def pause(self, i=0):
        ps = [p for p in self.s['parts'] if 'pause' in p]
        return ps[i]['at'] - self.s['start']
    def a(self, n, kind, rel, **extra):
        anims.append((f'#{self.id(n)}', kind, self.s['start'] + rel, extra))

PH = {'F1': 'sophie_pink_lachend_dissertation.jpg', 'F2': 'sophie_schwarz_ganzkoerper_tuer.jpg',
      'F3': 'sophie_schwarz_nah_buch.jpg', 'F4': 'sophie_pink_lesend.jpg', 'F5': 'sophie_pink_baum.jpg'}
COL = {'blau': ('#77C5D8', '#DAEEF3'), 'gruen': ('#ADCA2A', '#E9F0C1'), 'magenta': ('#EE6A87', '#FBD0D3'), 'gelb': ('#FCC300', '#FFF0BE')}

def photo(c, n, f, x, y, w, h, pos='50% 20%', kb=0.06, radius=24, rel=0.0):
    c.a(n, 'in', rel)
    c.a(n + '-img', 'kb', 0, scale=1 + kb, d=c.s['dur'])
    return (f'<div id="{c.id(n)}" class="photo" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;border-radius:{radius}px">'
            f'<img id="{c.id(n + "-img")}" src="media/{PH[f]}" style="object-position:{pos}"></div>')

def chat(c, n, sender, lines, x, y, w, label='Fiktives Beispiel', extra_cls='', fs=27):
    body = ''.join(f'<p>{l}</p>' for l in lines)
    return (f'<div id="{c.id(n)}" class="chat {extra_cls}" style="left:{x}px;top:{y}px;width:{w}px;font-size:{fs}px">'
            f'<div class="chat-head"><span class="dot"></span><span class="dot"></span><span class="dot"></span>'
            f'<b>{sender}</b><span class="label">{label}</span></div><div class="chat-body">{body}</div></div>')

def card(c, n, text, x, y, w, bg='#F0F0F0', fs=34, cls='', h=None, bar=None):
    hh = f'height:{h}px;' if h else ''
    bb = f'border-left:10px solid {bar};' if bar else ''
    return f'<div id="{c.id(n)}" class="card {cls}" style="left:{x}px;top:{y}px;width:{w}px;{hh}background:{bg};font-size:{fs}px;{bb}">{text}</div>'

def stop_card(c, n, text, x, y, w, rel):
    c.a(n, 'pop', rel)
    return f'<div id="{c.id(n)}" class="stop" style="left:{x}px;top:{y}px;width:{w}px"><span class="stop-icon">❚❚</span>{text}</div>'

def source(c, text, rel=1.0):
    c.a('src', 'in', rel)
    return f'<div id="{c.id("src")}" class="source">{text}</div>'

def H(x, color):  # Hervorhebung
    return f'<span class="mark" style="background:{COL[color][1]}">{x}</span>'

CH = {1: ('Einstieg', 'magenta'), 2: ('Meine Haltung', 'gelb'), 3: ('Vor dem Prompt', 'blau'), 4: ('Vier Anwendungen', 'gruen'),
      5: ('Prüfen und weitergeben', 'blau'), 6: ('Zusammenfassung', 'gelb'), 7: ('Abschluss und Kontakt', 'magenta')}

def chapter_of(s):
    if s['id'] == 'Zwischenbild': return 4
    return int(s['id'][0])

def scene_html(s):
    c = Sc(s); i = s['id']; D = s['dur']
    h = ''
    if i == '1.1':
        title = 'KI nutzen. Selber denken. Verantwortung übernehmen.'.split(' ')
        spans = ''
        for k, w in enumerate(title):
            spans += f'<span id="{c.id("t" + str(k))}" class="tw">{E(w)}</span> '
            c.a('t' + str(k), 'in', 0.3 + k * 0.28)
        h += f'<div class="title-xl" style="top:300px">{spans}</div>'
        for k, (col, x, w) in enumerate([('blau', 380, 330), ('gruen', 830, 420), ('magenta', 1260, 330)]):
            h += f'<div id="{c.id("u" + str(k))}" class="uline" style="left:{x}px;top:{520 if k < 2 else 520}px;width:{w}px;background:{COL[col][0]}"></div>'
            c.a('u' + str(k), 'grow', 2.6 + k * 0.3)
        h += f'<div id="{c.id("sub")}" class="center-text" style="top:580px;font-size:36px;color:#333">Ein Erklärvideo von Dr. Sophie Hundertmark</div>'
        c.a('sub', 'in', 3.2)
        h += card(c, 'note', 'KI-generiertes Video auf Grundlage der Position von Dr. Sophie Hundertmark.', 460, 680, 1000, fs=30, cls='center')
        c.a('note', 'in', 0.8)
    elif i == '1.2':
        h += photo(c, 'ph', 'F1', 200, 160, 380, 650, pos='50% 25%')
        h += card(c, 'task', '<div class="kicker">Aufgabe</div>Vorschlag für einen<br>30-Minuten-Workshop', 760, 300, 900, fs=56, bar=COL['magenta'][0])
        c.a('task', 'in', c.kw('Workshop') - 0.2)
        h += f'<div id="{c.id("q")}" class="center-text" style="left:760px;width:900px;top:560px;text-align:left;font-size:40px">Zwei mögliche Antworten …</div>'
        c.a('q', 'in', c.kw('Zurück'))
    elif i == '1.3':
        h += f'<div class="tag" style="left:860px;top:150px">Fiktive Beispiele</div>'
        long = ['Liebes Team, vielen herzlichen Dank für die tolle Gelegenheit! Im Folgenden findet ihr eine umfassende, ganzheitliche Übersicht über zahlreiche innovative Möglichkeiten, wie wir den Workshop gestalten könnten:',
                '<b>1. Icebreaker-Bingo</b> – fördert garantiert die Dynamik! <b>2. KI-Quiz</b> mit 40 Fragen. <b>3. Gruppenarbeit</b> (siehe unten!!) <b>4. Impulsvortrag</b> …',
                '<b>WICHTIG:</b> Studien zeigen, dass KI <u>garantiert 50 % Zeit spart</u>. 5. Rollenspiel 6. World Café 7. Speed-Dating mit Prompts 8. Fishbowl …',
                '9. Design Thinking Sprint 10. Galerie 11. Barcamp 12. Abschlussrunde mit Feedbackbogen, Fotoprotokoll und Zertifikat. Zusammenfassend lässt sich sagen, dass all diese Ideen …',
                'Darüber hinaus wäre es empfehlenswert, ergänzend auch noch folgende Aspekte zu berücksichtigen: Zielgruppe, Raum, Catering, Technik, Nachhaltigkeit, Evaluation …']
        inner = ''.join(f'<p>{l}</p>' for l in long)
        h += (f'<div id="{c.id("a")}" class="chat" style="left:150px;top:220px;width:780px;height:470px;font-size:24px">'
              f'<div class="chat-head"><span class="dot"></span><span class="dot"></span><span class="dot"></span><b>Nachricht A</b><span class="label">612 Wörter</span></div>'
              f'<div class="chat-body clipbox"><div id="{c.id("scroll")}">{inner}</div></div></div>')
        c.a('a', 'in', 0.3); c.a('scroll', 'scroll', 0.8, y=-330, d=c.kw('Rechts') - 0.8)
        h += chat(c, 'b', 'Nachricht B', ['Hallo Team, mein Vorschlag: Wir vergleichen zwei Nachrichten und überarbeiten eine davon gemeinsam.',
                                         '<b>Ablauf:</b> 5 / 10 / 10 / 5 Minuten.', '<b>Offen:</b> Raum und Technik.',
                                         '<b>KI-Hinweis:</b> Ideen und Kürzung mit KI, geprüft von mir.'], 990, 220, 780, label='', fs=27)
        c.a('b', 'in', c.kw('Rechts'))
        h += f'<div id="{c.id("q")}" class="center-text" style="top:720px;font-size:46px;font-weight:700">Welche Nachricht hilft dir wirklich weiter?</div>'
        c.a('q', 'in', c.kw('Welche'))
        c.a('think', 'pop', c.pause())
        h += f'<div id="{c.id("think")}" class="stop" style="left:810px;top:400px;width:300px"><span class="stop-icon">❚❚</span>Kurz überlegen</div>'
    elif i == '1.4':
        h += f'<div id="{c.id("from")}" class="person" style="left:200px;top:330px"><div class="avatar" style="background:{COL["gelb"][1]}">✉</div>Absender</div>'
        h += f'<div id="{c.id("to")}" class="person" style="left:1440px;top:330px"><div class="avatar" style="background:{COL["magenta"][1]}">Du</div>Empfänger</div>'
        c.a('from', 'in', 0.2); c.a('to', 'in', 0.5)
        h += f'<div id="{c.id("arrow")}" class="arrow" style="left:470px;top:420px;width:900px"></div>'
        c.a('arrow', 'grow', 0.9)
        h += f'<div id="{c.id("msg")}" class="mini-doc" style="left:520px;top:350px">Nachricht A<br><small>612 Wörter</small></div>'
        c.a('msg', 'in', 0.7); c.a('msg', 'move', 1.4, x=640, d=2.0)
        for k, (wd, lab) in enumerate([('lesen', 'lesen'), ('sortieren', 'sortieren'), ('prüfen', 'prüfen'), ('korrigieren', 'korrigieren')]):
            h += f'<div id="{c.id("k" + str(k))}" class="chip" style="left:{1180 + (k % 2) * 250}px;top:{560 + (k // 2) * 90}px;background:{COL["magenta"][1]}">{lab}</div>'
            rel = c.kw(wd) if wd != 'korrigieren' else c.kw('prüfen') + 0.7
            c.a('k' + str(k), 'pop', rel)
        h += f'<div id="{c.id("lab")}" class="center-text" style="top:240px;font-size:44px;font-weight:700">Denkarbeit weitergereicht</div>'
        c.a('lab', 'in', c.kw('weitergereicht') - 0.6)
    elif i == '2.1':
        h += f'<div id="{c.id("bgf")}" class="block" style="left:1080px;top:200px;width:620px;height:600px;background:{COL["gelb"][1]}"></div>'
        c.a('bgf', 'in', 0.0); c.a('bgf', 'move', 0.7, y=-40, d=D - 0.7)
        h += photo(c, 'ph', 'F1', 1180, 150, 400, 660, pos='50% 25%')
        h += f'<div id="{c.id("name")}" class="name" style="left:150px;top:220px">Dr. Sophie Hundertmark</div>'
        c.a('name', 'in', 0.3)
        for k, (wd, lab, col) in enumerate([('Ideen', 'Ideen sammeln', 'blau'), ('strukturieren', 'Strukturieren', 'gruen'), ('Sicht', 'Neue Perspektiven', 'magenta')]):
            h += card(c, 'c' + str(k), lab, 150, 360 + k * 120, 640, bg=COL[col][1], fs=40)
            c.a('c' + str(k), 'in', c.kw(wd) - 0.2)
        h += f'<div id="{c.id("go")}" class="name" style="left:150px;top:730px;font-size:48px;color:{COL["magenta"][0]}">Nutzt KI!</div>'
        c.a('go', 'pop', c.kw('Nutzt'))
    elif i == '2.2':
        h += f'<div class="col-head" style="left:150px;top:170px">Das kann KI beitragen</div>'
        h += f'<div class="col-head" style="left:1000px;top:170px">Das bleibt bei mir</div>'
        for k, lab in enumerate(['Ideen', 'Entwürfe', 'Rückfragen']):
            h += card(c, 'l' + str(k), lab, 150, 260 + k * 115, 700, fs=38)
            c.a('l' + str(k), 'in', 0.3 + k * 0.3)
        for k, (wd, lab, col) in enumerate([('Wählt', 'Auswahl', 'gelb'), ('verstanden', 'Verständnis', 'blau'), ('geprüft', 'Prüfung', 'gruen'), ('Verantwortung', 'Verantwortung', 'magenta')]):
            h += card(c, 'r' + str(k), lab, 1000, 260 + k * 115, 760, bg=COL[col][1], fs=38, bar=COL[col][0])
        c.a('r1', 'in', c.kw('verstanden')); c.a('r2', 'in', c.kw('geprüft')); c.a('r0', 'in', c.kw('Wählt')); c.a('r3', 'in', c.kw('Verantwortung'))
        h += source(c, 'Menschliche Handlungsfähigkeit im Zentrum: vgl. UNESCO 2023', 1.5)
    elif i == '2.3':
        h += f'<div class="path-label" style="left:150px;top:220px">Überlegungen überspringen</div>'
        h += f'<div id="{c.id("p1")}" class="arrow grey" style="left:640px;top:250px;width:420px"></div>'
        h += card(c, 'r1', 'weniger Übung im Begründen', 1100, 205, 660, fs=36)
        c.a('p1', 'grow', 0.4); c.a('r1', 'in', c.kw('Begründen') - 0.3)
        h += f'<div id="{c.id("l2")}" class="path-label" style="left:150px;top:480px">Mit KI weiterdenken</div>'
        h += f'<div id="{c.id("p2")}" class="arrow" style="left:640px;top:510px;width:420px"></div>'
        c.a('l2', 'in', c.kw('stärken') - 0.4); c.a('p2', 'grow', c.kw('stärken'))
        for k, (wd, lab, col) in enumerate([('Rückfragen', 'Rückfragen', 'blau'), ('Feedback', 'Feedback', 'gruen'), ('Sichtweisen', 'andere Sichtweisen', 'magenta')]):
            h += f'<div id="{c.id("c" + str(k))}" class="chip" style="left:{1100}px;top:{400 + k * 95}px;background:{COL[col][1]}">{lab}</div>'
            c.a('c' + str(k), 'pop', c.kw(wd) - 0.1)
        h += source(c, 'Menschliche Handlungsfähigkeit im Zentrum: vgl. UNESCO 2023', 0.5)
    elif i in ('2.4', '6.3'):
        lines = [('KI nutzen.', 'blau'), ('Selber denken.', 'gruen'), ('Verantwortung übernehmen.', 'magenta')]
        keys = ['nutzen', 'Selber', 'Verantwortung'] if i == '2.4' else None
        for k, (txt, col) in enumerate(lines):
            h += f'<div id="{c.id("l" + str(k))}" class="motto" style="top:{230 + k * 150}px;background:{COL[col][1]}">{txt}</div>'
            c.a('l' + str(k), 'in', (c.kw(keys[k]) - 0.3) if keys else 0.4 + k * 0.9)
        if i == '2.4':
            h += f'<div id="{c.id("lead")}" class="center-text" style="top:160px;font-size:32px;color:#444">Mein Leitsatz für unsere Zusammenarbeit</div>'
            c.a('lead', 'in', 0.3)
            h += photo(c, 'ph', 'F1', 1580, 580, 200, 200, pos='50% 18%', radius=100, rel=0.5)
    elif i == '3.1':
        h += photo(c, 'ph', 'F2', 160, 150, 380, 670, pos='50% 0%')
        c.a('ph-img', 'pan', 0, y=-60, d=D)
        h += '<div class="col-head" style="left:700px;top:170px">Ziel klären</div>'
        h += '<div class="hint" style="left:700px;top:240px">Prompt = deine Eingabe an die KI</div>'
        for k, (wd, q) in enumerate([('entstehen', 'Was soll entstehen?'), ('Für', 'Für wen?'), ('lernen', 'Was will ich selbst lernen?'), ('Informationen', 'Welche Informationen braucht es wirklich?')]):
            h += card(c, 'q' + str(k), f'<span class="num" style="background:{COL["blau"][0]}">{k + 1}</span>{q}', 700, 320 + k * 115, 1060, fs=38)
            c.a('q' + str(k), 'in', c.kw(wd) - 0.6)
    elif i == '3.2':
        h += f'<div id="{c.id("box")}" class="panel" style="left:260px;top:160px;width:1400px;height:620px;border-top:12px solid {COL["blau"][0]}"><div class="col-head" style="position:static;margin-bottom:24px">Vor Upload oder Eingabe prüfen</div></div>'
        c.a('box', 'in', 0.2)
        qs = [('freigegeben', 'Ist das Tool für diesen Einsatz freigegeben?'), ('verarbeitet', 'Dürfen diese Daten dort verarbeitet werden?'),
              ('Personen', 'Sind Personen erkennbar?'), ('gespeichert', 'Was ist über Speicherung, Zugriff und Weiterverwendung (z.&nbsp;B. Training) bekannt?')]
        for k, (wd, q) in enumerate(qs):
            h += f'<div id="{c.id("q" + str(k))}" class="check" style="left:320px;top:{280 + k * 115}px;width:1280px"><span class="box"><span id="{c.id("v" + str(k))}" class="tick">✓</span></span>{q}</div>'
            c.a('q' + str(k), 'in', c.kw(wd) - 1.0); c.a('v' + str(k), 'pop', c.kw(wd) + 0.6)
        h += source(c, 'Vgl. EDÖB: KI im Alltag; Einsatz von ChatGPT (2023)')
    elif i == '3.3':
        h += '<div class="tag" style="left:150px;top:170px">Fiktives Beispiel</div>'
        h += (f'<div id="{c.id("sent")}" class="sentence" style="left:150px;top:240px;width:1620px">'
              f'<span class="rel"><span id="{c.id("n")}">Frau M.</span><span id="{c.id("strike")}" class="strike"></span></span>, '
              f'<span class="rel"><span id="{c.id("h0")}" class="hlbg"></span>Leiterin</span> der '
              f'<span class="rel"><span id="{c.id("h1")}" class="hlbg"></span>Abteilung X in Y</span>, war '
              f'<span class="rel"><span id="{c.id("h2")}" class="hlbg"></span>im März krank</span>.</div>')
        c.a('sent', 'in', 0.2); c.a('strike', 'grow', c.kw('Namen'))
        for k, wd in enumerate(['Funktion', 'Ort', 'Ereignis']):
            c.a('h' + str(k), 'hl', c.kw(wd))
        h += f'<div id="{c.id("exp")}" class="center-text" style="left:150px;width:1620px;text-align:left;top:420px;font-size:38px">Auch diese Details machen eine Person erkennbar.</div>'
        c.a('exp', 'in', c.kw('erkennbar') - 0.3)
        h += card(c, 'tip', 'Unsicher? Erst klären oder mit fiktiven Daten arbeiten.', 150, 560, 1300, bg=COL['blau'][1], fs=40, bar=COL['blau'][0])
        c.a('tip', 'in', c.kw('unsicher'))
    elif i == '4.0':
        h += '<div class="col-head" style="left:150px;top:160px">Unser fiktives Beispiel</div>'
        facts = [('dreissig', '⏱', '30 Minuten'), ('zwölf', '👥', '12 Erwachsene'), ('Account', '🔒', 'kein eigener KI-Account nötig'), ('Raum', '?', 'Raum und Technik offen')]
        for k, (wd, ic, lab) in enumerate(facts):
            h += f'<div id="{c.id("f" + str(k))}" class="fact" style="left:{150 + k * 420}px;top:240px"><div class="fact-ic">{ic}</div>{lab}</div>'
            c.a('f' + str(k), 'in', c.kw(wd) - 0.3)
        tiles = [('A', 'Brainstorming', 'gelb'), ('B', 'Kritisch hinterfragen', 'blau'), ('C', 'Entwurf erstellen', 'gruen'), ('D', 'Unterlagen für andere', 'magenta')]
        for k, (L, lab, col) in enumerate(tiles):
            h += f'<div id="{c.id("t" + str(k))}" class="tile" style="left:{150 + k * 420}px;top:540px;background:{COL[col][1]}"><b>{L}</b>{lab}</div>'
            c.a('t' + str(k), 'in', c.kw('vier') + 0.2 + k * 0.25)
    elif i == '4.A':
        P = c.s['parts']
        # Teil 1: eigene Ideen
        b1 = c.kw('Mein') - 0.2  # Beginn Teil 2
        b2 = c.kw('Antwort') - 0.2
        b3 = c.kw('Probier') - 0.2
        h += f'<div id="{c.id("g1")}" class="group">'
        h += f'<div class="note" style="left:760px;top:180px"><div class="note-head">Meine Ideen</div>'
        h += f'<div id="{c.id("i1")}">1&nbsp; Nachrichtenvergleich</div><div id="{c.id("i2")}">2&nbsp; Gemeinsame Fehlersuche</div></div>'
        h += f'<div class="tile-head" style="left:150px;top:180px"><b>A</b>Brainstorming:<br>erst ich, dann KI</div></div>'
        c.a('g1', 'in', 0.2); c.a('i1', 'in', c.kw('Nachrichtenvergleich') - 0.2); c.a('i2', 'in', c.kw('Fehlersuche') - 0.3)
        c.a('g1', 'out', b1 - 0.5)
        # Teil 2: Prompt
        h += f'<div id="{c.id("g2")}" class="group">'
        h += chat(c, 'p1', 'Ich', [f'{H("Ich plane einen 30-minütigen Workshop für zwölf Erwachsene.", "gruen")} {H("Ziel: KI-Ergebnisse prüfen, sinnvoll kürzen und KI-Nutzung offenlegen.", "blau")} {H("Meine eigenen Ideen sind ein Nachrichtenvergleich und eine gemeinsame Fehlersuche.", "gruen")}'], 150, 170, 1620, label='Prompt · Teil 1', fs=30)
        h += chat(c, 'p2', 'Ich', [f'{H("Schlage fünf weitere unterschiedliche Aktivitäten vor. Nenne jeweils Nutzen, Nachteil und Zeitbedarf.", "blau")} {H("Ein eigener KI-Account darf nicht nötig sein. Wähle noch nichts für mich aus.", "magenta")}'], 150, 470, 1620, label='Prompt · Teil 2', fs=30)
        h += '<div class="legend" style="left:150px;top:755px"><span style="background:#DAEEF3">Ziel</span><span style="background:#E9F0C1">Kontext</span><span style="background:#FBD0D3">Grenze</span></div></div>'
        c.a('g2', 'in', b1); c.a('p1', 'in', b1); c.a('p2', 'in', c.kw('Für', 1) - 0.3 if False else c.kw('verlange') - 1.0)
        c.a('g2', 'out', b2 - 0.5)
        # Teil 3: Antwort-Tabelle
        rows = [('Nachrichtenvergleich (meine Idee)'.replace(' (', '<br>('), 'Nutzen direkt erlebbar', 'braucht gute Beispiele', '10 Min', 'gewählt', 'gruen'),
                ('Rollenspiel', 'lebendig', 'viel Vorbereitung', '20 Min', 'weggelassen: zu viel Vorbereitung', 'magenta'),
                ('Prompt-Duell', 'spielerisch', 'braucht KI-Zugang', '10 Min', '', ''),
                ('Quellen-Detektiv', 'schult Prüfen', 'Recherche nötig', '15 Min', '', ''),
                ('Stille Post mit KI-Text', 'zeigt Verzerrung', 'wenig Tiefe', '10 Min', '', ''),
                ('Galerie-Rundgang', 'alle aktiv', 'Platzbedarf', '15 Min', '', '')]
        tr = ''
        for k, (a1, a2, a3, a4, st, col) in enumerate(rows):
            stamp = f'<span id="{c.id("st" + str(k))}" class="stamp" style="background:{COL[col][1]};border-color:{COL[col][0]}">{st}</span>' if st else ''
            tr += f'<tr><td>{a1}</td><td>{a2}</td><td>{a3}</td><td>{a4}</td><td class="stampcell">{stamp}</td></tr>'
        h += (f'<div id="{c.id("g3")}" class="group"><div class="tag" style="left:150px;top:160px">Konstruierte Beispielantwort</div>'
              f'<table class="tbl" style="left:150px;top:220px;width:1620px"><tr><th>Aktivität</th><th>Nutzen</th><th>Nachteil</th><th>Zeit</th><th>Meine Bewertung</th></tr>{tr}</table></div>')
        c.a('g3', 'in', b2); c.a('st0', 'pop', c.kw('Nachrichtenvergleich', 2)); c.a('st1', 'pop', c.kw('Rollenspiel'))
        c.a('g3', 'out', b3 - 0.4)
        h += stop_card(c, 'stop', 'Dein Zug: Notiere zwei eigene Ideen, bevor du KI fragst.', 360, 330, 1200, b3)
    elif i == 'Zwischenbild':
        n = sum(1 for x in scenes[:s['idx']] if x['id'] == 'Zwischenbild')
        f, txt = [('F5', 'Erst selber denken. Dann KI.'), ('F3', 'Kritik selbst bewerten.'), ('F4', 'Nachrechnen. Nachlesen. Nachfragen.')][n]
        h += photo(c, 'ph', f, 300, 150, 380, 670, pos='50% 20%')
        h += f'<div id="{c.id("t")}" class="interlude" style="left:800px;top:400px;width:900px">{txt}</div>'
        c.a('t', 'in', 0.5)
    elif i == '4.B':
        b2 = c.kw('Beispielantwort') - 0.3
        h += f'<div id="{c.id("g1")}" class="group">'
        h += f'<div class="tile-head" style="left:150px;top:170px"><b>B</b>Konzept kritisch hinterfragen</div>'
        h += chat(c, 'p1', 'Ich', [f'{H("Prüfe dieses Workshop-Konzept kritisch.", "blau")} Benenne drei konkrete Schwächen, unausgesprochene Annahmen und eine ernstzunehmende Gegenposition.'], 150, 300, 1620, label='Prompt · Teil 1', fs=30)
        h += chat(c, 'p2', 'Ich', [f'Unterscheide Angaben aus meinem Konzept von deinen Vermutungen. Welche Aussagen muss ich unabhängig prüfen? Schlage Verbesserungen mit wenig Zusatzaufwand vor. {H("Bestätige mein Konzept nicht einfach.", "magenta")}'], 150, 520, 1620, label='Prompt · Teil 2', fs=30)
        h += '</div>'
        c.a('g1', 'in', 0.2); c.a('p1', 'in', c.kw('bitte') - 0.4); c.a('p2', 'in', c.kw('schreibe') - 0.3)
        c.a('g1', 'out', b2 - 0.4)
        h += f'<div id="{c.id("g2")}" class="group"><div class="tag" style="left:150px;top:160px">Konstruierte Beispielantwort</div>'
        crit = [('zugang', 'Nicht alle haben Zugang zu einem KI-Tool.', 'übernehme ich: gemeinsame Demo', 'gruen'),
                ('Wettbewerb', 'Mit einem Wettbewerb steigt die Motivation.', 'passt hier nicht: lenkt vom Lernziel ab', 'magenta'),
                ('Kritik', 'Annahme: Alle kennen Begriffe wie «Prompt».', 'übernehme ich: kurze Begriffsklärung', 'gruen')]
        for k, (wd, ktxt, ev, col) in enumerate(crit):
            y = 230 + k * 150
            h += card(c, 'k' + str(k), ktxt, 150, y, 860, fs=32)
            h += f'<div id="{c.id("e" + str(k))}" class="eval" style="left:1060px;top:{y}px;width:710px;background:{COL[col][1]};border-color:{COL[col][0]}">{ev}</div>'
        c.a('g2', 'in', b2)
        for k in range(3): c.a('k' + str(k), 'in', b2 + 0.3 + k * 0.4)
        c.a('e0', 'pop', c.kw('Demo') - 0.4); c.a('e1', 'pop', c.kw('übernehme', 1) if False else c.kw('ablenkt') - 0.5); c.a('e2', 'pop', c.kw('Kritik') - 0.2)
        h += card(c, 'merk', '<b>Kritik hilft beim Prüfen. Sie ersetzt die Prüfung nicht.</b>', 150, 700, 1620, bg=COL['gelb'][1], fs=36, cls='center')
        c.a('merk', 'in', c.kw('bewerte') - 0.6)
        h += '</div>'
    elif i == '4.C':
        b2 = c.kw('Ich', 1) - 0.2  # Prompt
        b3 = c.kw('Schaut') - 0.2
        b4 = c.kw('Zehn', 1) - 0.2 if False else c.pause() + 3.0 - 0.1
        h += f'<div id="{c.id("g1")}" class="group"><div class="tile-head" style="left:150px;top:170px"><b>C</b>Einen Entwurf erstellen</div>'
        for k, (wd, lab, col) in enumerate([('Ziel', 'Ziel', 'blau'), ('Kontext', 'Kontext', 'gruen'), ('Material', 'Material', 'gelb'), ('Grenzen', 'Grenzen', 'magenta'), ('Ausgabeformat', 'Ausgabeformat', 'blau')]):
            h += f'<div id="{c.id("b" + str(k))}" class="tile small" style="left:{150 + k * 330}px;top:350px;background:{COL[col][1]}">{lab}</div>'
            c.a('b' + str(k), 'pop', c.kw(wd) - 0.1)
        h += '</div>'
        c.a('g1', 'in', 0.2); c.a('g1', 'out', b2 - 0.4)
        h += f'<div id="{c.id("g2")}" class="group">'
        h += chat(c, 'p1', 'Ich', [f'Erstelle einen Ablaufentwurf für den Workshop. {H("Zielgruppe: zwölf Erwachsene.", "gruen")} {H("Lernziel: eine KI-Antwort prüfen, kürzen und transparent weitergeben.", "blau")} {H("Dauer: insgesamt 30 Minuten. Kein eigener KI-Account erforderlich.", "gruen")}'], 150, 170, 1620, label='Prompt · Teil 1', fs=30)
        h += chat(c, 'p2', 'Ich', [f'{H("Ausgabe als Tabelle mit Zeit, Aktivität, Ziel und Material.", "blau")} {H("Erfinde keine Quellen, Zahlen oder Zusagen.", "magenta")} Liste fehlende Angaben als offene Punkte.'], 150, 470, 1620, label='Prompt · Teil 2', fs=30)
        h += '</div>'
        c.a('g2', 'in', b2); c.a('p2', 'in', c.kw('Tabelle') - 0.5); c.a('g2', 'out', b3 - 0.4)
        h += f'<div id="{c.id("g3")}" class="group"><div class="tag" style="left:150px;top:160px">Konstruierte Beispielantwort</div>'
        h += ('<table class="tbl" style="left:150px;top:220px;width:900px"><tr><th>Zeit</th><th>Aktivität</th></tr>'
              '<tr><td>10 Min</td><td>Einstieg</td></tr><tr><td>15 Min</td><td>Prüfung</td></tr><tr><td>15 Min</td><td>Austausch</td></tr>'
              '<tr class="total"><td colspan="2">Total: 30 Minuten</td></tr></table>')
        h += f'<div id="{c.id("calc")}" class="calc" style="left:1110px;top:300px">10 + 15 + 15 = <span class="mark" style="background:{COL["magenta"][1]}">40</span></div>'
        h += ('<div id="' + c.id('fix') + '" class="group">'
              f'<table class="tbl" style="left:1110px;top:420px;width:660px;background:{COL["gruen"][1]}"><tr><th>Zeit</th><th>Aktivität · korrigiert</th></tr>'
              '<tr><td>5 Min</td><td>Einstieg</td></tr><tr><td>10 Min</td><td>Prüfung</td></tr><tr><td>10 Min</td><td>Überarbeitung</td></tr><tr><td>5 Min</td><td>Austausch</td></tr>'
              '<tr class="total"><td colspan="2">Total: 30 Minuten · offen: Raum, Technik</td></tr></table></div></div>')
        c.a('g3', 'in', b3); c.a('calc', 'pop', b4); c.a('fix', 'in', c.kw('korrigiere') - 0.2)
        h += stop_card(c, 'stop', 'Fällt dir etwas auf?', 1180, 300, 520, c.pause())
        c.a('stop', 'out0', b4 - 0.2)
    elif i == '4.D':
        b2 = c.kw('Darum') - 0.2
        b3 = c.kw('Genau') - 0.2
        h += f'<div id="{c.id("g1")}" class="group"><div class="tile-head" style="left:150px;top:170px"><b>D</b>Unterlagen für andere</div>'
        h += f'<div id="{c.id("blur")}" class="blurchat" style="left:150px;top:300px"><div class="stamp" style="position:absolute;left:60px;top:200px;background:{COL["magenta"][1]};border-color:{COL["magenta"][0]}">braucht das Team nicht</div></div>'
        h += f'<div id="{c.id("doc")}" class="doc" style="left:900px;top:170px"><div class="doc-title">Unterlage für das Organisationsteam</div>'
        for k, lab in enumerate(['Ziel', 'Ablauf', 'Vorbereitung', 'Offene Punkte']):
            h += f'<div id="{c.id("d" + str(k))}" class="doc-line"><b>{lab}</b><span></span></div>'
        h += f'<div id="{c.id("d4")}" class="doc-ki">KI-Hinweis</div></div></div>'
        c.a('g1', 'in', 0.2); c.a('blur', 'in', c.kw('Chatverlauf') - 0.4); c.a('doc', 'in', c.kw('Seite') - 0.3)
        for k in range(5): c.a('d' + str(k), 'in', c.kw('Seite') + 0.3 + k * 0.35)
        c.a('g1', 'out', b2 - 0.4)
        h += f'<div id="{c.id("g2")}" class="group">'
        h += chat(c, 'p1', 'Ich', [f'Erstelle aus diesem geprüften Ablauf eine kurze Unterlage für das Organisationsteam. {H("Sie sollen danach den Workshop vorbereiten können.", "blau")} Maximal eine Seite, etwa 250 Wörter.'], 150, 170, 1620, label='Prompt · Teil 1', fs=30)
        h += chat(c, 'p2', 'Ich', [f'Struktur: Ziel, Ablauf, Vorbereitung, offene Punkte. {H("Ergänze keine neuen Fakten oder Zusagen.", "magenta")} Schreibe direkt und verständlich. Benenne den tatsächlichen KI-Einsatz in einem separaten kurzen Hinweis.'], 150, 450, 1620, label='Prompt · Teil 2', fs=30)
        h += '</div>'
        c.a('g2', 'in', b2); c.a('p2', 'in', c.kw('Danach') - 0.3); c.a('g2', 'out', b3 - 0.4)
        h += f'<div id="{c.id("g3")}" class="group"><div class="col-head" style="left:150px;top:170px">Aufwand aller Beteiligten</div>'
        bars = [('Erstellen', 1, 3), ('Prüfen', 1, 2), ('Lesen', 5, 1), ('Nacharbeiten', 5, 1)]
        for k, (lab, a, bb) in enumerate(bars):
            y = 280 + k * 105
            h += f'<div class="bar-lab" style="left:150px;top:{y}px">{lab}</div>'
            h += f'<div id="{c.id("ba" + str(k))}" class="bar" style="left:460px;top:{y}px;width:{a * 110}px;background:{COL["magenta"][1]}"></div>'
            h += f'<div id="{c.id("bb" + str(k))}" class="bar" style="left:1140px;top:{y}px;width:{bb * 110}px;background:{COL["gruen"][1]}"></div>'
        h += '<div class="bar-head" style="left:460px;top:235px">Nachricht A</div><div class="bar-head" style="left:1140px;top:235px">Nachricht B</div>'
        h += f'<div id="{c.id("eff")}" class="center-text" style="top:720px;font-size:44px;font-weight:700">Effizienz = Aufwand aller Beteiligten</div></div>'
        c.a('g3', 'in', b3)
        for k, wd in enumerate(['Erstellen', 'Prüfen', 'Lesen', 'Nacharbeiten']):
            c.a('ba' + str(k), 'grow', c.kw(wd) - 0.2); c.a('bb' + str(k), 'grow', c.kw(wd) - 0.2)
        c.a('eff', 'in', c.kw('schnell') - 0.3)
    elif i == '5.1':
        h += photo(c, 'ph', 'F4', 150, 150, 380, 670, pos='50% 20%')
        h += '<div class="col-head" style="left:640px;top:170px">Bevor ich weitergebe, prüfe ich</div>'
        qs = [('Fakten', 'Fakten und Zahlen stimmen?'), ('Gibt', 'Quellen existieren und stützen die Aussage?'), ('Annahmen', 'Welche Annahmen wurden ergänzt?'),
              ('offen', 'Was ist noch offen?'), ('verständlich', 'Für die empfangende Person verständlich und hilfreich?')]
        for k, (wd, q) in enumerate(qs):
            h += f'<div id="{c.id("q" + str(k))}" class="check" style="left:640px;top:{250 + k * 95}px;width:1130px;font-size:34px"><span class="box"><span id="{c.id("v" + str(k))}" class="tick">✓</span></span>{q}</div>'
            c.a('q' + str(k), 'in', c.kw(wd) - 0.3); c.a('v' + str(k), 'pop', c.kw(wd) + 1.0)
        h += (f'<div id="{c.id("ex")}" class="exline" style="left:640px;top:740px"><span class="rel">«Alle Teilnehmenden haben einen KI-Zugang»'
              f'<span id="{c.id("exs")}" class="strike"></span></span> → <b id="{c.id("exn")}">Kein eigener Account nötig</b></div>')
        c.a('ex', 'in', c.kw('Annahmen') + 0.4); c.a('exs', 'grow', c.kw('offen') - 0.2); c.a('exn', 'in', c.kw('offen') + 0.3)
    elif i == '5.2':
        h += '<div class="col-head" style="left:150px;top:170px">Zwei Fallen</div>'
        h += card(c, 'w0', '<span class="num" style="background:#FCC300">1</span>Eine zweite Antwort derselben KI ist keine unabhängige Bestätigung.', 150, 260, 1620, bg=COL['gelb'][1], fs=40)
        h += card(c, 'w1', '<span class="num" style="background:#FCC300">2</span>«Erfinde nichts» ist keine Garantie.', 150, 410, 1620, bg=COL['gelb'][1], fs=40)
        h += f'<div id="{c.id("g")}" class="center-text" style="top:580px;font-size:52px;font-weight:700">Gute Sprache ist kein Beleg.</div>'
        h += card(c, 'r', 'Keine belastbare Grundlage? Streichen oder als offen markieren.', 360, 700, 1200, fs=32, cls='center')
        c.a('w0', 'in', c.kw('Erstens') - 0.2); c.a('w1', 'in', c.kw('Zweitens') - 0.2); c.a('g', 'pop', c.kw('Gute') - 0.1); c.a('r', 'in', c.kw('Findet') - 0.2)
    elif i == '5.3':
        h += f'<div id="{c.id("doc")}" class="doc" style="left:510px;top:160px;width:900px;height:640px"><div class="doc-title">Unterlage für das Organisationsteam</div>'
        for lab in ['Ziel', 'Ablauf', 'Vorbereitung', 'Offene Punkte']:
            h += f'<div class="doc-line"><b>{lab}</b><span></span></div>'
        h += (f'<div id="{c.id("ki")}" class="ki-box"><b>KI-Hinweis</b><br>KI wurde für Ideen, einen Ablaufentwurf und sprachliche Kürzung genutzt. '
              f'Auswahl, Überarbeitung und Prüfung habe ich übernommen. Noch offen: Raum und Technik.</div></div>')
        c.a('doc', 'in', 0.2); c.a('ki', 'pop', c.kw('KI-Hinweis') - 0.3)
    elif i == '5.4':
        h += '<div class="col-head" style="left:150px;top:170px">Ein KI-Hinweis …</div>'
        h += card(c, 'y', '✓&nbsp; macht Zusammenarbeit nachvollziehbar', 150, 260, 780, bg=COL['gruen'][1], fs=38, bar=COL['gruen'][0])
        h += card(c, 'n0', '✕&nbsp; ersetzt keine Prüfung', 990, 260, 780, bg=COL['magenta'][1], fs=38, bar=COL['magenta'][0])
        h += card(c, 'n1', '✕&nbsp; macht unzulässige Nutzung nicht zulässig', 990, 390, 780, bg=COL['magenta'][1], fs=38, bar=COL['magenta'][0])
        h += card(c, 'f', 'Für Studienleistungen: jeweilige Dokumentations- und Prüfungsregeln beachten.', 150, 600, 1620, fs=32)
        c.a('y', 'in', 0.4); c.a('n0', 'in', c.kw('ersetzt') - 0.3); c.a('n1', 'in', c.kw('Nutzung') - 0.3); c.a('f', 'in', c.kw('Studienleistungen') - 0.3)
        h += source(c, 'Vgl. z.&nbsp;B. Richtlinien der HSLU-Departemente W (2024) und D&amp;K (2024); es gelten die Vorgaben des eigenen Moduls.', c.kw('Studienleistungen'))
    elif i == '6.1':
        h += '<div class="col-head" style="left:150px;top:165px">Fünf Fragen vor jeder Übergabe</div>'
        qs = [('Darf', 'Darf ich diese Daten in diesem Tool verwenden?', 'blau'), ('Habe', 'Habe ich alles gelesen und verstanden?', 'gruen'),
              ('relevante', 'Habe ich relevante Fakten und Quellen geprüft?', 'magenta'), ('Übergabe', 'Ist die Übergabe kurz, verständlich und hilfreich?', 'gelb'),
              ('transparent', 'Ist mein KI-Einsatz transparent?', 'blau')]
        for k, (wd, q, col) in enumerate(qs):
            h += card(c, 'q' + str(k), f'<span class="num" style="background:{COL[col][0]}">{k + 1}</span>{q}', 150, 240 + k * 112, 1620, bg=COL[col][1], fs=36)
            rel = c.kw(wd, 2 if wd == 'Übergabe' else 1) - 0.3
            if k == 4: rel = c.kw('Und', 1) - 0.1
            c.a('q' + str(k), 'in', rel)
    elif i == '6.2':
        h += photo(c, 'ph', 'F3', 1390, 150, 380, 670, pos='50% 20%')
        for k, (wd, lab, col) in enumerate([('Verständnis', 'Gemeinsames Verständnis', 'blau'), ('sinnvoll', 'Sinnvoll, verantwortungsvoll, transparent', 'gruen'), ('Qualität', 'Mehr Qualität. Echte Effizienz. Für alle.', 'magenta')]):
            h += card(c, 'c' + str(k), lab, 150, 220 + k * 135, 1150, bg=COL[col][1], fs=40, bar=COL[col][0])
            c.a('c' + str(k), 'in', c.kw(wd) - 0.4)
        h += card(c, 'bm', 'Begleitmaterial: alle Prompts, Prüffragen und Quellen', 150, 660, 1150, fs=32)
        c.a('bm', 'in', c.kw('Prompts') - 0.4)
    elif i == '7.1':
        h += photo(c, 'ph', 'F5', 150, 160, 380, 650, pos='50% 25%', kb=0.03)
        h += (f'<div id="{c.id("info")}" class="contact" style="left:610px;top:250px"><div class="name" style="position:static;font-size:52px">Dr. Sophie Hundertmark</div>'
              '<p>sophie@hundertmark.ch</p><p>WhatsApp: +41 78 900 5346</p><p>www.sophiehundertmark.com</p></div>')
        h += (f'<div class="qrwrap" style="left:1340px;top:220px"><img src="media/qr_whatsapp.png" width="440" height="440">'
              '<div class="qrcap">Fragen? Schreib mir auf WhatsApp.</div></div>')
        c.a('info', 'in', 0.3)
        h += (f'<div id="{c.id("credits")}" class="credits" style="top:760px">Stimme: elevenlabs.io · Mit KI erstellt. Fotos: bereitgestellte Aufnahmen von Sophie Hundertmark.</div>')
        c.a('credits', 'in', max(D - 7.0, 21.0))
    return h

# ---------- Komposition ----------
body = []
for s in scenes:
    body.append(f'<div class="clip scene" id="sc{s["idx"]}" data-start="{s["start"]:.3f}" data-duration="{s["dur"]:.3f}" data-track-index="1">{scene_html(s)}</div>')

# Kapitelmarken
chapters = []
for s in scenes:
    ch = chapter_of(s)
    if not chapters or chapters[-1][0] != ch: chapters.append([ch, s['start'], s['start'] + s['dur']])
    else: chapters[-1][2] = s['start'] + s['dur']
for n, (ch, st, en) in enumerate(chapters, 1):
    name, col = CH[ch]
    body.append(f'<div class="clip chapter" data-start="{st:.3f}" data-duration="{en - st:.3f}" data-track-index="2"><span class="ch-num">{n}</span>{name}<div class="ch-line" style="background:{COL[col][0]}"></div></div>')

# Untertitel
for k, cue in enumerate(cues):
    left = 'left:150px;width:1100px;transform:none;' if cue['s'] >= scenes[-1]['start'] else ''
    spans = ''
    for j, w in enumerate(cue['words']):
        wid = f'w{k}_{j}'
        spans += f'<span class="sw"><span id="{wid}" class="swbg"></span>{E(w["w"])}</span> '
        anims.append((f'#{wid}', 'on', w['s'], {}))
        anims.append((f'#{wid}', 'off', max(w['e'], w['s'] + 0.08), {}))
    body.append(f'<div class="clip subs" style="{left}" data-start="{cue["s"]:.3f}" data-duration="{cue["e"] - cue["s"]:.3f}" data-track-index="3"><div class="subs-in">{spans}</div></div>')

# ---------- Animationen ----------
js = []
for sel, kind, at, ex in anims:
    at = max(0.0, at)
    if kind == 'in':
        js.append(f'tl.fromTo("{sel}",{{opacity:0,y:28}},{{opacity:1,y:0,duration:0.6,ease:"power2.out"}},{at:.3f});')
    elif kind == 'pop':
        js.append(f'tl.fromTo("{sel}",{{opacity:0,scale:0.85}},{{opacity:1,scale:1,duration:0.45,ease:"back.out(1.7)"}},{at:.3f});')
    elif kind == 'out':
        js.append(f'tl.to("{sel}",{{opacity:0,duration:0.4,ease:"power1.in"}},{at:.3f});')
    elif kind == 'out0':
        js.append(f'tl.to("{sel}",{{opacity:0,duration:0.25}},{at:.3f});')
    elif kind == 'kb':
        js.append(f'tl.fromTo("{sel}",{{scale:1}},{{scale:{ex["scale"]},duration:{ex["d"]:.3f},ease:"none"}},{at:.3f});')
    elif kind == 'pan':
        js.append(f'tl.fromTo("{sel}",{{y:0}},{{y:{ex["y"]},duration:{ex["d"]:.3f},ease:"none",immediateRender:false}},{at:.3f});')
    elif kind == 'grow':
        js.append(f'tl.fromTo("{sel}",{{scaleX:0}},{{scaleX:1,duration:0.7,ease:"power2.out"}},{at:.3f});')
    elif kind == 'scroll':
        js.append(f'tl.fromTo("{sel}",{{y:0}},{{y:{ex["y"]},duration:{ex["d"]:.3f},ease:"none"}},{at:.3f});')
    elif kind == 'move':
        js.append(f'tl.to("{sel}",{{x:{ex.get("x", 0)},y:{ex.get("y", 0)},duration:{ex["d"]:.3f},ease:"power1.inOut"}},{at:.3f});')
    elif kind == 'hl':
        js.append(f'tl.fromTo("{sel}",{{opacity:0}},{{opacity:1,duration:{ex.get("d", 0.3)}}},{at:.3f});')
    elif kind == 'on':
        js.append(f'tl.set("{sel}",{{opacity:1}},{at:.3f});')
    elif kind == 'off':
        js.append(f'tl.set("{sel}",{{opacity:0}},{at:.3f});')
    elif kind == 'unhl':
        js.append(f'tl.to("{sel}",{{opacity:0,duration:0.12}},{at:.3f});')

# Szenenübergänge: weiches Einblenden jeder Szene
for s in scenes:
    js.append(f'tl.fromTo("#sc{s["idx"]}",{{opacity:0}},{{opacity:1,duration:0.35}},{s["start"]:.3f});')
    js.append(f'tl.to("#sc{s["idx"]}",{{opacity:0,duration:0.3}},{s["start"] + s["dur"] - 0.3:.3f});' if s['id'] != '7.1' else '')

css = open('style.css', encoding='utf-8').read()
page = f'''<!doctype html>
<html lang="de">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1920, height=1080" />
<title>KI nutzen. Selber denken. Verantwortung übernehmen.</title>
<script src="node_modules/gsap/dist/gsap.min.js"></script>
<style>
{css}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL:.3f}" data-width="1920" data-height="1080">
<audio id="vo" class="clip" src="narration{SUF}.wav" data-start="0" data-duration="{TOTAL:.3f}" data-track-index="0" data-volume="1"></audio>
<div class="clip chrome" data-start="0" data-duration="{TOTAL:.3f}" data-track-index="4">
  <img class="logo-hm" src="media/hundertmark_logo.png" alt="Hundertmark">
  <img class="logo-hslu" src="media/HSLU_Logo_DE_Schwarz.jpg" alt="HSLU">
  <div class="footer">Dr. Sophie Hundertmark · www.sophiehundertmark.com</div>
</div>
{chr(10).join(body)}
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(x for x in js if x)}
tl.to({{}}, {{duration: 0.01}}, {TOTAL - 0.01:.3f});
window.__timelines["main"] = tl;
tl.seek(0);
</script>
</body>
</html>
'''
open('kurzversion.html' if SHORT else 'index.html', 'w', encoding='utf-8').write(page)
print(f'Gesamtdauer {TOTAL:.1f}s ({int(TOTAL // 60)}:{int(TOTAL % 60):02d}), Szenen {len(scenes)}, Untertitel {len(cues)}, Animationen {len(js)}')
