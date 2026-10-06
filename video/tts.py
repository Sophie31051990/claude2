import json, os, sys, base64, urllib.request, subprocess
KEY = open('/tmp/claude-0/-home-user-claude2/0d7da328-a233-5985-9fc7-28894543dd87/scratchpad/.elevenlabs_key').read().strip()
VOICE = 'EXAVITQu4vr4xnSDxMaL'  # Sarah (premade)
MODEL = 'eleven_multilingual_v2'
scenes = json.load(open('scenes.json', encoding='utf-8'))
only = sys.argv[1:]
def speak(text):
    return text.replace('sophie@hundertmark.ch', 'sophie at hundertmark punkt c h')
for si, s in enumerate(scenes):
    if only and s['id'] not in only: continue
    for pi, p in enumerate(s['parts']):
        if 'text' not in p: continue
        base = f'audio/s{si:02d}_p{pi}'
        if os.path.exists(base + '.json'): continue
        body = json.dumps({'text': speak(p['text']), 'model_id': MODEL, 'language_code': 'de',
            'voice_settings': {'stability': 0.55, 'similarity_boost': 0.75, 'style': 0.15, 'use_speaker_boost': True, 'speed': 0.95}}).encode()
        req = urllib.request.Request(f'https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/with-timestamps?output_format=mp3_44100_128',
            data=body, headers={'xi-api-key': KEY, 'Content-Type': 'application/json'})
        try:
            r = json.load(urllib.request.urlopen(req, timeout=120))
        except urllib.error.HTTPError as e:
            print('ERR', s['id'], pi, e.code, e.read()[:300]); sys.exit(1)
        open(base + '.mp3', 'wb').write(base64.b64decode(r['audio_base64']))
        json.dump({'display': p['text'], 'spoken': speak(p['text']), 'alignment': r.get('alignment')}, open(base + '.json', 'w', encoding='utf-8'), ensure_ascii=False)
        print('ok', s['id'], pi, r['alignment']['character_end_times_seconds'][-1])
