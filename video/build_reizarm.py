# Reizarme Fassung (für autistische Zuschauende): gleicher Sprechertext, aber
# eine Aussage pro Bild, keine Daueranzeigen, keine Bewegung, längere Pausen.
# Erzeugt narration_reizarm.wav, ..._reizarm.srt, timing_reizarm.json, reizarm.html.
import json, os, re, subprocess, html

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
# SHORT=1: Kurzversion (gleiche Szenenauswahl wie build.py), nur bestehende Aufnahmen
SHORT = os.environ.get('SHORT') == '1'
KEEP = ['1.1', '1.2', '1.3', '1.4', '2.1', '2.2', '2.4', '3.1', '5.2', '6.1', '7.1']
SUF = '_reizarm_Kurzversion' if SHORT else '_reizarm'

LEAD, GAP, TAIL = 1.2, 1.4, 1.8   # Sekunden: vor dem Sprechen, zwischen Absätzen, nach der Szene
SENT_PAUSE = 0.8                  # zusätzliche Stille nach jedem Satz
INTRO = 4.0                       # ruhiges Titelbild vor dem ersten Wort
FIXED = {'Zwischenbild': 5.0, '6.3': 8.0}
CREDITS = 7.0                     # Abspann nach der Schlusskarte
XF = 0.6                          # Überblendung zwischen Bildern
BEAT_EARLY = 0.45                 # Bildwechsel kurz vor dem Stichwort (in der Satzpause)

scenes = json.load(open('scenes.json', encoding='utf-8'))
for si, s in enumerate(scenes): s['aidx'] = si
if SHORT: scenes = [s for s in scenes if s['id'] in KEEP]

def dur(path):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]).decode())

EMAIL_SPOKEN = ['sophie', 'at', 'hundertmark', 'punkt', 'c', 'h']

def chunks_and_words(js, total):
    """Teilt eine Aufnahme an Satzenden. Gibt Abschnitte (t0, t1) und Wörter je Abschnitt zurück."""
    al = js['alignment']
    ch, st, en = al['characters'], al['character_start_times_seconds'], al['character_end_times_seconds']
    cuts = []
    for i, c in enumerate(ch):
        if c in '.?!' and (i + 1 == len(ch) or ch[i + 1].isspace()):
            j = i + 1
            while j < len(ch) and ch[j].isspace(): j += 1
            if j < len(ch):
                cuts.append(((en[i] + st[j]) / 2, j))
    bounds = [0.0] + [c[0] for c in cuts] + [total]
    starts = [0] + [c[1] for c in cuts]
    chunks = []
    for k in range(len(bounds) - 1):
        a = starts[k]; b = starts[k + 1] if k + 1 < len(starts) else len(ch)
        words, cur = [], None
        for c, s0, e0 in zip(ch[a:b], st[a:b], en[a:b]):
            if c.isspace():
                if cur: words.append(cur); cur = None
                continue
            if cur is None: cur = {'w': '', 's': s0, 'e': e0}
            cur['w'] += c; cur['e'] = e0
        if cur: words.append(cur)
        i = 0
        while i <= len(words) - 6:
            if [re.sub(r'\W', '', x['w']).lower() for x in words[i:i + 6]] == EMAIL_SPOKEN:
                words[i:i + 6] = [{'w': 'sophie@hundertmark.ch', 's': words[i]['s'], 'e': words[i + 5]['e']}]
            i += 1
        chunks.append({'t0': bounds[k], 't1': bounds[k + 1], 'words': words})
    return chunks

# ---------- Timing ----------
t = 0.0
segments = []   # (abs_start, file, t0, t1)
for si, s in enumerate(scenes):
    s['idx'] = si; s['start'] = t; s['words'] = []; s['sentences'] = []
    if s['id'] in FIXED:
        s['dur'] = FIXED[s['id']]; t += s['dur']; continue
    c = t + (INTRO if si == 0 else LEAD)
    first = True
    for pi, p in enumerate(s['parts']):
        if 'pause' in p:
            p['at'] = c; c += p['pause'] + 1.0; continue
        if not first: c += GAP
        first = False
        f = f'audio/s{s["aidx"]:02d}_p{pi}.mp3'
        js = json.load(open(f'audio/s{s["aidx"]:02d}_p{pi}.json', encoding='utf-8'))
        chunks = chunks_and_words(js, dur(f))
        for k, chk in enumerate(chunks):
            if k: c += SENT_PAUSE
            off = c - chk['t0']
            segments.append((c, f, chk['t0'], chk['t1']))
            ws = [{'w': w['w'], 's': w['s'] + off, 'e': w['e'] + off} for w in chk['words']]
            s['words'] += ws
            if ws: s['sentences'].append(ws)
            c += chk['t1'] - chk['t0']
    end = c + TAIL
    if s['id'] == '7.1': end += CREDITS
    s['dur'] = round(end - t, 3)
    t = s['start'] + s['dur']
TOTAL = round(t, 3)

# ---------- Sprachspur ----------
inputs, filt = [], []
for i, (st0, f, a, b) in enumerate(segments):
    inputs += ['-i', f]
    ms = int(round(st0 * 1000))
    filt.append(f'[{i}:a]atrim={a:.4f}:{b:.4f},asetpts=PTS-STARTPTS,aresample=44100,aformat=channel_layouts=mono,'
                f'afade=t=in:d=0.02,afade=t=out:st={max(0, b - a - 0.03):.4f}:d=0.03,adelay={ms}|{ms}[a{i}]')
filt.append(''.join(f'[a{i}]' for i in range(len(segments))) + f'amix=inputs={len(segments)}:normalize=0,apad,atrim=0:{TOTAL}[out]')
script = os.path.join('renders', f'filter{SUF}.txt'); os.makedirs('renders', exist_ok=True)
open(script, 'w').write(';'.join(filt))
subprocess.check_call(['ffmpeg', '-y', '-v', 'error', *inputs, '-filter_complex_script', script, '-map', '[out]', '-ar', '44100', '-ac', '2', f'narration{SUF}.wav'])

# ---------- Untertitel: ein Satz pro Einblendung, ohne Wort-Hervorhebung ----------
MAXC = 90
cues = []
def split_sentence(ws):
    # Lange Sätze ausgewogen teilen, bevorzugt nach einem Komma nahe der Mitte
    if len(' '.join(x['w'] for x in ws)) <= MAXC or len(ws) < 4: return [ws]
    total = len(' '.join(x['w'] for x in ws)); best = None
    for i in range(2, len(ws) - 1):
        left = len(' '.join(x['w'] for x in ws[:i]))
        score = abs(left - total / 2) - (25 if ws[i - 1]['w'].endswith((',', ':', ';')) else 0)
        if best is None or score < best[0]: best = (score, i)
    i = best[1]
    return split_sentence(ws[:i]) + split_sentence(ws[i:])
for s in scenes:
    for sent in s['sentences']:
        cues += split_sentence(sent)
for i, c in enumerate(cues):
    nxt = cues[i + 1][0]['s'] - 0.05 if i + 1 < len(cues) else TOTAL
    cues[i] = {'words': c, 's': max(0, c[0]['s'] - 0.1), 'e': min(c[-1]['e'] + 0.7, nxt)}

def srt_t(x):
    ms = int(round(x * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); sec, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{sec:02d},{ms:03d}'
with open(f'KI_nutzen_selber_denken_Sophie_Hundertmark{SUF}.srt', 'w', encoding='utf-8') as f:
    for i, c in enumerate(cues, 1):
        f.write(f"{i}\n{srt_t(c['s'])} --> {srt_t(c['e'])}\n{' '.join(w['w'] for w in c['words'])}\n\n")

# ---------- Bausteine ----------
E = html.escape
PH = {'F1': 'sophie_pink_lachend_dissertation.jpg', 'F2': 'sophie_schwarz_ganzkoerper_tuer.jpg',
      'F3': 'sophie_schwarz_nah_buch.jpg', 'F4': 'sophie_pink_lesend.jpg', 'F5': 'sophie_pink_baum.jpg'}

def big(text, sub=None):
    s = f'<div class="b-sub">{sub}</div>' if sub else ''
    return f'<div class="b-center"><div class="b-big">{text}</div>{s}</div>'

def quote(text):
    return f'<div class="b-center"><div class="b-quote">{text}</div></div>'

def lst(head, items):
    li = ''.join(f'<li>{x}</li>' for x in items)
    return f'<div class="b-center"><div class="b-head">{head}</div><ul class="b-list">{li}</ul></div>'

def section(n, text):
    return f'<div class="b-center"><div class="b-num">{n}</div><div class="b-big">{text}</div></div>'

def question(n, text):
    return f'<div class="b-center"><div class="b-count">Frage {n} von 5</div><div class="b-big">{text}</div></div>'

def mark(ok, text, sub=None):
    sym = '<span class="b-ok">✓</span>' if ok else '<span class="b-no">✕</span>'
    s = f'<div class="b-sub">{sub}</div>' if sub else ''
    return f'<div class="b-center"><div class="b-big">{sym}{text}</div>{s}</div>'

def photo(f, text, sub=None, pos='50% 20%'):
    s = f'<div class="b-sub left">{sub}</div>' if sub else ''
    return (f'<div class="b-photo"><img src="media/{PH[f]}" style="object-position:{pos}"></div>'
            f'<div class="b-side"><div class="b-big left">{text}</div>{s}</div>')

def table(rows, total, head=None):
    tr = ''.join(f'<tr><td>{a}</td><td>{b}</td></tr>' for a, b in rows)
    h = f'<div class="b-head">{head}</div>' if head else ''
    return f'<div class="b-center">{h}<table class="b-table">{tr}<tr class="tot"><td colspan="2">{total}</td></tr></table></div>'

def table_q(rows, total, q):
    tr = ''.join(f'<tr><td>{a}</td><td>{b}</td></tr>' for a, b in rows)
    return f'<div class="b-center"><table class="b-table">{tr}<tr class="tot"><td colspan="2">{total}</td></tr></table><div class="b-sub strong">{q}</div></div>'

def messages(which):
    a = '<div class="b-msg"><div class="b-msg-h">Nachricht A</div>' + '<span class="ln"></span>' * 11 + '<div class="b-msg-f">lang, viele Ideen, unklar</div></div>'
    b = ('<div class="b-msg short"><div class="b-msg-h">Nachricht B</div><p>Ein Vorschlag.</p><p>Ein Ablauf.</p><p>Eine offene Frage.</p>'
         '<div class="b-msg-f">kurz und klar</div></div>')
    if which == 'a': return f'<div class="b-center"><div class="b-row">{a}</div></div>'
    if which == 'b': return f'<div class="b-center"><div class="b-row">{b}</div></div>'
    return f'<div class="b-center"><div class="b-row">{a}{b}</div><div class="b-sub strong">Welche Nachricht hilft dir wirklich weiter?</div></div>'

MOTTO = ('<div class="b-center"><div class="b-motto" style="background:#DAEEF3">KI nutzen.</div>'
         '<div class="b-motto" style="background:#E9F0C1">Selber denken.</div>'
         '<div class="b-motto" style="background:#FBD0D3">Verantwortung übernehmen.</div></div>')

LOGOS = '<img class="b-logo-l" src="media/hundertmark_logo.png"><img class="b-logo-r" src="media/HSLU_Logo_DE_Schwarz.jpg">'

TITLE = (LOGOS + '<div class="b-center"><div class="b-title">KI nutzen. Selber denken.<br>Verantwortung übernehmen.</div>'
         '<div class="b-sub">Ein Erklärvideo von Dr. Sophie Hundertmark</div></div>')

CONTACT_A = (LOGOS + '<div class="b-photo"><img src="media/sophie_pink_baum.jpg" style="object-position:50% 25%"></div>'
             '<div class="b-side"><div class="b-big left">Dr. Sophie Hundertmark</div></div>')
CONTACT_B = (LOGOS + '<div class="b-contact"><div class="b-contact-text"><div class="b-head left">Fragen?</div>'
             '<p>E-Mail:<br><b>sophie@hundertmark.ch</b></p><p>WhatsApp:<br><b>QR-Code scannen</b></p></div>'
             '<img class="b-qr" src="media/qr_whatsapp.png" width="440" height="440"></div>')
CREDITS_HTML = (LOGOS + '<div class="b-center"><div class="b-big">Danke fürs Zuschauen.</div>'
                '<div class="b-sub">Dr. Sophie Hundertmark · www.sophiehundertmark.com</div>'
                '<div class="b-small">Mit KI erstellt. Stimme: elevenlabs.io. Fotos: bereitgestellte Aufnahmen von Sophie Hundertmark.<br>'
                'Prompts, Prüffragen und Quellen: im Begleitmaterial.</div></div>')

# Pro Szene: Liste von (Stichwort, Vorkommen, HTML). Stichwort None = Szenenbeginn.
B = {
 '1.1': [(None, 1, TITLE), ('Hinweis', 1, big('Dieses Video ist KI-generiert.', 'Die Stimme ist eine KI-Stimme.<br>Die Inhalte sind die Position von Dr. Sophie Hundertmark.'))],
 '1.2': [(None, 1, photo('F1', 'Ihr plant einen Workshop.', pos='50% 25%')), ('Zurück', 1, big('Zwei mögliche Antworten'))],
 '1.3': [(None, 1, messages('a')), ('Rechts', 1, messages('b')), ('Welche', 1, messages('ab'))],
 '1.4': [(None, 1, lst('Bei der langen Nachricht musst du:', ['lesen', 'sortieren', 'prüfen'])),
         ('andere', 1, big('Die eine Person spart Zeit.', 'Die andere hat mehr Arbeit.')),
         ('eigentliche', 1, big('Die Denkarbeit wird nur weitergereicht.'))],
 '2.1': [(None, 1, photo('F1', 'Dr. Sophie Hundertmark', pos='50% 25%')),
         ('hilft', 1, lst('KI hilft mir:', ['Ideen sammeln', 'Gedanken strukturieren', 'eine andere Sicht bekommen'])),
         ('Genau', 1, big('Nutzt KI!'))],
 '2.2': [(None, 1, big('Ein KI-Ergebnis ist noch kein gutes Arbeitsergebnis.')),
         ('Was', 1, lst('Was ihr weitergebt, habt ihr selbst:', ['gelesen', 'verstanden', 'geprüft'])),
         ('Wählt', 1, big('Auswählen, was die andere Person braucht.')),
         ('sagt', 1, big('Offen sagen, wofür ihr KI genutzt habt.')),
         ('Für', 1, big('Ihr übernehmt die Verantwortung.'))],
 '2.3': [(None, 1, big('Überlegungen überspringen heisst:', 'weniger Übung im Begründen und Entscheiden.')),
         ('kann', 1, lst('KI kann das Lernen stärken:', ['Rückfragen', 'Feedback', 'andere Sichtweisen']))],
 '2.4': [(None, 1, big('Mein Leitsatz')), ('nutzen', 1, MOTTO)],
 '3.1': [(None, 1, photo('F2', 'Vor dem Prompt:<br>Ziel klären', 'Prompt = deine Eingabe an die KI', pos='50% 0%')),
         ('Was', 1, big('Was soll entstehen?', 'Für wen ist es?')),
         ('möchte', 1, big('Was will ich selbst lernen?')), ('welche', 1, big('Welche Informationen braucht es wirklich?'))],
 '3.2': [(None, 1, big('Daten prüfen')), ('Ist', 1, big('Ist das Tool freigegeben?')),
         ('Dürfen', 1, big('Dürfen die Daten dort verarbeitet werden?')), ('Sind', 1, big('Sind Personen erkennbar?')),
         ('weiss', 1, big('Was passiert mit den Eingaben?', 'Speicherung, Zugriff, Training'))],
 '3.3': [(None, 1, big('Nur den Namen löschen reicht nicht immer.')),
         ('Auch', 1, lst('Auch das macht eine Person erkennbar:', ['Funktion', 'Ort', 'besonderes Ereignis'])),
         ('Wenn', 1, big('Unsicher? Vorher klären.', 'Oder mit einem fiktiven Beispiel arbeiten.'))],
 '4.0': [(None, 1, big('Unser fiktives Beispiel:', 'Eine Gruppe plant einen Workshop.')),
         ('Dreissig', 1, lst('Der Workshop:', ['30 Minuten', '12 Erwachsene'])),
         ('Niemand', 1, big('Kein eigener KI-Account nötig.')), ('Raum', 1, big('Raum und Technik sind noch offen.')),
         ('Daran', 1, big('Vier Anwendungen'))],
 '4.A': [(None, 1, section(1, 'Brainstorming')), ('starte', 1, big('Erst ich, dann KI.')),
         ('Zwei', 1, lst('Meine Ideen:', ['Nachrichtenvergleich', 'Gemeinsame Fehlersuche'])),
         ('frage', 1, big('Dann frage ich die KI.')),
         ('Mein', 1, lst('Mein Prompt nennt:', ['Ziel und Gruppe', 'Zeit', 'meine eigenen Ideen'])),
         ('verlange', 1, lst('Für jede neue Idee:', ['Nutzen', 'Nachteil', 'Zeitbedarf'])),
         ('ausdrücklich', 1, quote('«Wähle noch nichts für mich aus.»')),
         ('Antwort', 1, big('Die KI liefert fünf Vorschläge.')), ('übernehme', 1, big('Ich wähle selbst aus.')),
         ('nehme', 1, mark(True, 'Nachrichtenvergleich', 'Die Gruppe erlebt den Nutzen direkt.')),
         ('Rollenspiel', 1, mark(False, 'Rollenspiel', 'zu viel Vorbereitung')),
         ('Probier', 1, big('Probier es selbst:', 'Zuerst zwei eigene Ideen notieren.<br>Dann die KI fragen.'))],
 '4.B': [(None, 1, section(2, 'Konzept kritisch hinterfragen')), ('Hier', 1, big('KI als Gegenüber,', 'das unbequeme Fragen stellt.')),
         ('bitte', 1, lst('Ich bitte um:', ['Schwächen', 'unausgesprochene Annahmen', 'eine Gegenposition'])),
         ('schreibe', 1, quote('«Bestätige mein Konzept nicht einfach.»')),
         ('Beispielantwort', 1, big('Die KI sagt:', 'Nicht alle haben Zugang zu einem KI-Tool.')),
         ('nehme', 1, mark(True, 'Ich plane eine gemeinsame Demo.')),
         ('schlägt', 1, big('Die KI schlägt einen Wettbewerb vor.')),
         ('übernehme', 1, mark(False, 'Kein Wettbewerb.', 'Er lenkt vom Lernziel ab.')),
         ('Auch', 2, big('Auch die Kritik der KI bewerte ich selbst.'))],
 '4.C': [(None, 1, section(3, 'Einen Entwurf erstellen')),
         ('guter', 1, lst('Ein guter Prompt hat fünf Bausteine:', ['Ziel', 'Kontext', 'Material', 'Grenzen', 'Ausgabeformat'])),
         ('gebe', 1, big('Ich gebe nur an, was feststeht.')), ('wünsche', 1, big('Ich wünsche mir eine Tabelle.')),
         ('sage', 1, big('Nicht erlaubt:', 'erfundene Quellen, Zahlen oder Zusagen')),
         ('Schaut', 1, table([('Einstieg', '10 Minuten'), ('Prüfung', '15 Minuten'), ('Austausch', '15 Minuten')], 'Total: 30 Minuten', 'Die Antwort der KI:')),
         ('Fällt', 1, table_q([('Einstieg', '10 Minuten'), ('Prüfung', '15 Minuten'), ('Austausch', '15 Minuten')], 'Total: 30 Minuten', 'Fällt dir etwas auf?')),
         ('plus', 1, big('10 + 15 + 15 = 40', 'nicht 30')),
         ('klingt', 1, big('Die Antwort klingt sicher.', 'Und ist trotzdem falsch.')),
         ('korrigiere', 1, table([('Einstieg', '5 Minuten'), ('Prüfung', '10 Minuten'), ('Überarbeitung', '10 Minuten'), ('Austausch', '5 Minuten')], 'Total: 30 Minuten', 'Meine Korrektur:')),
         ('Freigabe', 1, big('Die Freigabe mache ich.', 'Nicht die KI.'))],
 '4.D': [(None, 1, section(4, 'Unterlagen für andere')),
         ('Organisationsteam', 1, big('Das Team braucht nicht den ganzen Chatverlauf.')),
         ('Seite', 1, big('Es braucht eine Seite zum Vorbereiten.')),
         ('Darum', 1, lst('Ich sage der KI:', ['Wer bekommt die Unterlage?', 'Was sollen die Personen damit tun?'])),
         ('Danach', 1, lst('Danach:', ['vollständig lesen', 'Wiederholungen streichen', 'Angaben prüfen'])),
         ('Team', 1, lst('Das Team sieht sofort:', ['was geplant ist', 'was vorzubereiten ist', 'was noch offen ist'])),
         ('Genau', 2, lst('Effizienz heisst: den Aufwand aller sehen.', ['Erstellen', 'Prüfen', 'Lesen', 'Nacharbeiten'])),
         ('schnell', 1, big('Schnell erzeugt ist nicht automatisch effizient.')),
         ('wurde', 1, big('Sonst wird Arbeit nur verschoben.'))],
 '5.1': [(None, 1, photo('F4', 'Vor dem Weitergeben:<br>prüfen')),
         ('Stimmen', 1, big('Stimmen Fakten und Zahlen?')), ('Gibt', 1, big('Gibt es die Quellen wirklich?')),
         ('Dafür', 1, big('Quelle öffnen und nachlesen.')), ('Welche', 1, big('Welche Annahmen hat die KI ergänzt?')),
         ('Was', 1, big('Was ist noch offen?')), ('Kurzfassung', 1, big('Ist es verständlich und hilfreich?'))],
 '5.2': [(None, 1, big('Zwei Fallen')),
         ('Erstens', 1, big('Falle 1', 'Eine zweite Antwort derselben KI ist keine Bestätigung.')),
         ('Zweitens', 1, big('Falle 2', '«Erfinde nichts» ist keine Garantie.')),
         ('Gute', 1, big('Gute Sprache ist kein Beleg.')),
         ('Findet', 1, big('Keine Grundlage gefunden?', 'Streichen oder als offen markieren.'))],
 '5.3': [(None, 1, big('Zum Schluss: ein kurzer KI-Hinweis')),
         ('wurde', 1, '<div class="b-center"><div class="b-note"><b>Beispiel für einen KI-Hinweis</b><p>KI wurde für Ideen, einen Ablaufentwurf und sprachliche Kürzung genutzt.</p>'
                      '<p>Auswahl, Überarbeitung und Prüfung habe ich übernommen.</p><p>Noch offen: Raum und Technik.</p></div></div>')],
 '5.4': [(None, 1, big('Ein KI-Hinweis gehört zu guter Zusammenarbeit.')),
         ('schreibt', 1, big('Nur schreiben, was ihr wirklich gemacht habt.')),
         ('ersetzt', 1, big('Ein Hinweis ersetzt keine Prüfung.')),
         ('macht', 1, big('Ein Hinweis macht nichts erlaubt,', 'was nach den Prüfungsregeln nicht erlaubt ist.')),
         ('Studienleistungen', 1, big('Für Studienleistungen gelten eigene Regeln.'))],
 '6.1': [(None, 1, big('Fünf Fragen vor jeder Übergabe')),
         ('Darf', 1, question(1, 'Darf ich diese Daten in diesem Tool verwenden?')),
         ('Habe', 1, question(2, 'Habe ich alles gelesen und verstanden?')),
         ('Habe', 2, question(3, 'Habe ich Fakten und Quellen geprüft?')),
         ('Ist', 1, question(4, 'Ist die Übergabe kurz, verständlich und hilfreich?')),
         ('KI-Einsatz', 1, question(5, 'Ist mein KI-Einsatz transparent?'))],
 '6.2': [(None, 1, photo('F3', 'Mein Wunsch')),
         ('gleiche', 1, big('Ein gemeinsames Verständnis von KI')),
         ('sinnvoll', 1, big('Sinnvoll, verantwortungsvoll, transparent')),
         ('gemeinsam', 1, big('Mehr Qualität.', 'Echte Effizienz. Für alle.')),
         ('Prompts', 1, big('Alles im Begleitmaterial:', 'Prompts, Fragen und Quellen')),
         ('unklar', 1, big('Etwas unklar?', 'Sprecht mich gern an.'))],
 '6.3': [(None, 1, MOTTO)],
 '7.1': [(None, 1, MOTTO), ('Das', 1, CONTACT_A), ('Wenn', 1, CONTACT_B)],
}
ZB = [('F5', 'Erst selber denken.<br>Dann KI.'), ('F3', 'Kritik selbst bewerten.'), ('F4', 'Nachrechnen.<br>Nachlesen.<br>Nachfragen.')]

def norm(x): return re.sub(r'[^\wäöüÄÖÜß]', '', x).lower()

def kw(s, word, n):
    k = 0
    for w in s['words']:
        if any(norm(part).startswith(norm(word)) for part in [w['w']] + w['w'].split('-')):
            k += 1
            if k == n: return w['s']
    raise SystemExit(f"Stichwort '{word}' ({n}) nicht in Szene {s['id']}")

beats = []  # (start, html)
zb = 0
for s in scenes:
    if s['id'] == 'Zwischenbild':
        f, txt = ZB[zb]; zb += 1
        beats.append([s['start'], photo(f, txt)]); continue
    for word, n, h in B[s['id']]:
        at = s['start'] if word is None else kw(s, word, n) - BEAT_EARLY
        if s['id'] == '7.1' and word == 'Wenn':
            beats.append([at, h]); beats.append([s['start'] + s['dur'] - CREDITS, CREDITS_HTML]); continue
        beats.append([at, h])
for i in range(1, len(beats)):
    if beats[i][0] <= beats[i - 1][0]: print('Reihenfolge stimmt nicht bei', round(beats[i][0], 1), 's')
beats.sort(key=lambda b: b[0])
short = []
for i, (st0, h) in enumerate(beats):
    en = beats[i + 1][0] if i + 1 < len(beats) else TOTAL
    if en - st0 < 2.5: short.append(f'{st0:.1f}s ({en - st0:.1f}s)')
qr = [b for b in beats if 'b-qr' in b[1]][0]
qr_dur = beats[beats.index(qr) + 1][0] - qr[0]

# ---------- Komposition ----------
body, js = [], []
for i, (st0, h) in enumerate(beats):
    en = beats[i + 1][0] + XF if i + 1 < len(beats) else TOTAL
    en = min(en, TOTAL)
    body.append(f'<div class="clip beat" id="b{i}" data-start="{st0:.3f}" data-duration="{en - st0:.3f}" data-track-index="1">{h}</div>')
    js.append(f'tl.fromTo("#b{i}",{{opacity:0}},{{opacity:1,duration:{XF},ease:"none"}},{st0:.3f});')
for k, cue in enumerate(cues):
    txt = E(' '.join(w['w'] for w in cue['words']))
    body.append(f'<div class="clip subs" data-start="{cue["s"]:.3f}" data-duration="{cue["e"] - cue["s"]:.3f}" data-track-index="2"><span>{txt}</span></div>')

css = open('style_reizarm.css', encoding='utf-8').read()
page = f'''<!doctype html>
<html lang="de">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1920, height=1080" />
<title>KI nutzen. Selber denken. Verantwortung übernehmen. (reizarme Fassung)</title>
<script src="node_modules/gsap/dist/gsap.min.js"></script>
<style>
{css}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL:.3f}" data-width="1920" data-height="1080">
<audio id="vo" class="clip" src="narration{SUF}.wav" data-start="0" data-duration="{TOTAL:.3f}" data-track-index="0" data-volume="1"></audio>
{chr(10).join(body)}
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(js)}
tl.to({{}}, {{duration: 0.01}}, {TOTAL - 0.01:.3f});
window.__timelines["main"] = tl;
tl.seek(0);
</script>
</body>
</html>
'''
open('kurzversion_reizarm.html' if SHORT else 'reizarm.html', 'w', encoding='utf-8').write(page)
json.dump({'total': TOTAL, 'beats': [round(b[0], 2) for b in beats], 'scenes': [{k: s[k] for k in ('id', 'title', 'start', 'dur')} for s in scenes]},
          open(f'timing{SUF}.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'Gesamtdauer {TOTAL:.1f}s ({int(TOTAL // 60)}:{int(TOTAL % 60):02d}), Bilder {len(beats)}, Untertitel {len(cues)}, QR-Standzeit {qr_dur:.1f}s')
if short: print('Kurze Bilder (<2.5s):', ', '.join(short))
