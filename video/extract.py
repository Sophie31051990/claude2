import re, json, sys
src = open('../docs/01_Sprechskript_und_Szenen.md', encoding='utf-8').read()
scenes = []
cur = None
for line in src.splitlines():
    m = re.match(r'^### (Szene [\d\.A-D]+|Zwischenbild)\s*·?\s*(.*?)\s*\((\d+:\d+)[–-]', line)
    if line.startswith('### '):
        title = line[4:]
        sid = re.match(r'(Szene\s+[\w\.]+|Zwischenbild)', title).group(1)
        cur = {'id': sid.replace('Szene ', ''), 'title': title, 'parts': []}
        scenes.append(cur)
        continue
    if cur is not None and line.startswith('> '):
        t = line[2:].strip()
        pm = re.match(r'\[Pause (\d+) Sekunden\]', t)
        if pm:
            cur['parts'].append({'pause': int(pm.group(1))})
        else:
            cur['parts'].append({'text': t})
out = [s for s in scenes]
json.dump(out, open('scenes.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
tot = 0
for s in out:
    n = sum(len(p.get('text', '')) for p in s['parts'])
    tot += n
    print(s['id'], n, s['title'][:60])
print('TOTAL', tot)
