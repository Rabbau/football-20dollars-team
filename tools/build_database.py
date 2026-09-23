"""Собирает базу футболистов из текущих составов клубов на английской Википедии.

Запуск из корня проекта:
    python tools/build_database.py          # составы -> data/players.json
    python tools/build_database.py --photos # плюс скачать фото в img/players/

Рейтинги берутся из tools/ratings.json (имя на английском -> рейтинг), у кого нет — 70.
Фото скачиваются только для тех, у кого файла ещё нет. Авторство фото пишется в img/players/CREDITS.md.
"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

HEADERS = {'User-Agent': 'team20dollars/1.0 (football auction game for GitHub Pages)'}
EN_API = 'https://en.wikipedia.org/w/api.php'
DB = 'data/players.json'
IMG_DIR = 'img/players'
RATINGS = 'tools/ratings.json'
DEFAULT_RATING = 70

# Статья клуба на en.wikipedia -> название по-русски
CLUBS = {
    'Real Madrid CF': 'Реал Мадрид',
    'FC Barcelona': 'Барселона',
    'Atlético Madrid': 'Атлетико',
    'Athletic Bilbao': 'Атлетик',
    'Manchester City F.C.': 'Манчестер Сити',
    'Liverpool F.C.': 'Ливерпуль',
    'Arsenal F.C.': 'Арсенал',
    'Chelsea F.C.': 'Челси',
    'Manchester United F.C.': 'Манчестер Юнайтед',
    'Tottenham Hotspur F.C.': 'Тоттенхэм',
    'Newcastle United F.C.': 'Ньюкасл',
    'Aston Villa F.C.': 'Астон Вилла',
    'FC Bayern Munich': 'Бавария',
    'Borussia Dortmund': 'Боруссия Д',
    'Bayer 04 Leverkusen': 'Байер',
    'Paris Saint-Germain FC': 'ПСЖ',
    'Inter Milan': 'Интер',
    'AC Milan': 'Милан',
    'Juventus FC': 'Ювентус',
    'SSC Napoli': 'Наполи',
    'Atalanta BC': 'Аталанта',
    'Al Nassr FC': 'Аль-Наср',
    'Al Hilal SFC': 'Аль-Хиляль',
}

# Где русская статья называется полным паспортным именем — пишем привычное
NAME_OVERRIDES = {
    'Endrick': 'Эндрик', 'Rodrygo': 'Родриго', 'Andriy Lunin': 'Андрей Лунин', 'Rodri': 'Родри',
    'Allan': 'Аллан', 'Abdukodir Khusanov': 'Абдукодир Хусанов', 'Víctor Muñoz': 'Виктор Муньос',
    'Estêvão': 'Эстевао', 'Mykhailo Mudryk': 'Михаил Мудрик', 'João Gomes': 'Жуан Гомес',
    'Alysson': 'Алисон', 'Luis Díaz': 'Луис Диас', 'Equi Fernández': 'Эсекьель Фернандес',
    'Illia Zabarnyi': 'Илья Забарный', 'Matvey Safonov': 'Матвей Сафонов', 'Luis Henrique': 'Луис Энрике',
    'Henrikh Mkhitaryan': 'Генрих Мхитарян', 'Carlos Augusto': 'Карлос Аугусто', 'Bremer': 'Бремер',
    'Giovane': 'Жиоване', 'Frank Anguissa': 'Франк Ангисса', 'Ayman Yahya': 'Айман Яхья', 'Bento': 'Бенто',
    'Juan Cabal': 'Хуан Кабаль', 'Joe Gomez': 'Джо Гомес', 'Freddie Woodman': 'Фредди Вудман',
    'Kostas Tsimikas': 'Костас Цимикас', 'Dani Vivian': 'Дани Вивиан', 'Yann Bisseck': 'Янн Биссек',
    'Erling Haaland': 'Эрлинг Холанд', 'Enzo dos Santos': 'Энцо дос Сантос', 'Alisson Becker': 'Алиссон',
    'Virgil van Dijk': 'Вирджил ван Дейк', 'Frenkie de Jong': 'Френки де Йонг', 'Matthijs de Ligt': 'Маттейс де Лигт',
    'Micky van de Ven': 'Микки ван де Вен', 'Jan Paul van Hecke': 'Ян Паул ван Хекке', 'Koni De Winter': 'Кони де Винтер',
}

POS = {'GK': 'GK', 'DF': 'DEF', 'MF': 'MID', 'FW': 'FWD'}

COUNTRIES = {
    'ALB': 'Албания', 'ALG': 'Алжир', 'ARG': 'Аргентина', 'AUS': 'Австралия', 'AUT': 'Австрия',
    'BEL': 'Бельгия', 'BIH': 'Босния и Герцеговина', 'BRA': 'Бразилия', 'BFA': 'Буркина-Фасо',
    'CAN': 'Канада', 'CHI': 'Чили', 'CIV': "Кот-д'Ивуар", 'CMR': 'Камерун', 'COD': 'ДР Конго',
    'COL': 'Колумбия', 'CRC': 'Коста-Рика', 'CRO': 'Хорватия', 'CZE': 'Чехия', 'DEN': 'Дания',
    'ECU': 'Эквадор', 'EGY': 'Египет', 'ENG': 'Англия', 'ESP': 'Испания', 'FIN': 'Финляндия',
    'FRA': 'Франция', 'GAB': 'Габон', 'GEO': 'Грузия', 'GER': 'Германия', 'GHA': 'Гана',
    'GRE': 'Греция', 'GUI': 'Гвинея', 'HUN': 'Венгрия', 'IRL': 'Ирландия', 'ISL': 'Исландия',
    'ISR': 'Израиль', 'ITA': 'Италия', 'JAM': 'Ямайка', 'JPN': 'Япония', 'KOR': 'Южная Корея',
    'KSA': 'Саудовская Аравия', 'KOS': 'Косово', 'MAR': 'Марокко', 'MEX': 'Мексика', 'MLI': 'Мали',
    'MNE': 'Черногория', 'NED': 'Нидерланды', 'NGA': 'Нигерия', 'NIR': 'Северная Ирландия',
    'NOR': 'Норвегия', 'NZL': 'Новая Зеландия', 'PAR': 'Парагвай', 'PER': 'Перу', 'POL': 'Польша',
    'POR': 'Португалия', 'ROU': 'Румыния', 'RUS': 'Россия', 'SCO': 'Шотландия', 'SEN': 'Сенегал',
    'SRB': 'Сербия', 'SUI': 'Швейцария', 'SVK': 'Словакия', 'SVN': 'Словения', 'SWE': 'Швеция',
    'TUN': 'Тунис', 'TUR': 'Турция', 'UKR': 'Украина', 'URU': 'Уругвай', 'USA': 'США',
    'UZB': 'Узбекистан', 'VEN': 'Венесуэла', 'WAL': 'Уэльс', 'ZAM': 'Замбия', 'CPV': 'Кабо-Верде',
    'ANG': 'Ангола', 'ARM': 'Армения', 'BUL': 'Болгария', 'CUW': 'Кюрасао', 'SUR': 'Суринам',
    'HAI': 'Гаити', 'HON': 'Гондурас', 'PAN': 'Панама', 'IRN': 'Иран', 'IRQ': 'Ирак', 'QAT': 'Катар',
    'UAE': 'ОАЭ', 'CHN': 'Китай', 'MKD': 'Северная Македония', 'LUX': 'Люксембург', 'EST': 'Эстония',
    'LTU': 'Литва', 'LVA': 'Латвия', 'CYP': 'Кипр', 'TOG': 'Того', 'BEN': 'Бенин', 'MOZ': 'Мозамбик',
    'RSA': 'ЮАР', 'ZIM': 'Зимбабве', 'KEN': 'Кения', 'EQG': 'Экваториальная Гвинея', 'GAM': 'Гамбия',
    'SLE': 'Сьерра-Леоне', 'GNB': 'Гвинея-Бисау', 'MTN': 'Мавритания', 'LBY': 'Ливия',
    'KAZ': 'Казахстан', 'ROM': 'Румыния', 'BOL': 'Боливия', 'DOM': 'Доминикана', 'TRI': 'Тринидад и Тобаго', 'CUB': 'Куба',
}


def get(url, params=None, raw=False):
    if params:
        url += '?' + urllib.parse.urlencode({**params, 'format': 'json', 'formatversion': 2})
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read() if raw else json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 7:
                raise
            time.sleep(int(e.headers.get('Retry-After') or 0) or 10 * (attempt + 1))


def squad_section(title):
    sections = get(EN_API, {'action': 'parse', 'page': title, 'prop': 'sections', 'redirects': 1})['parse']['sections']
    for s in sections:
        line = re.sub(r'<[^>]+>', '', s['line']).strip().lower()
        if line in ('current squad', 'first-team squad', 'first team squad', 'squad', 'players', 'current players'):
            text = get(EN_API, {'action': 'parse', 'page': title, 'prop': 'wikitext',
                                'section': s['index'], 'redirects': 1})['parse']['wikitext']
            # Только основная заявка: первый блок {{Fs start}} ... {{Fs end}}, без аренд и молодёжи
            m = re.search(r'\{\{\s*[Ff]s start.*?\{\{\s*[Ff]s end\s*\}\}', text, re.S)
            if m:
                return m.group(0)
    return ''


def parse_players(wikitext):
    players = []
    for m in re.finditer(r'\{\{\s*[Ff]s player\s*\|(.*?)\}\}\s*(?=\{\{|\n|$)', wikitext, re.S):
        body = m.group(1)
        fields = {}
        for part in re.split(r'\|(?![^\[]*\]\])', body):
            if '=' in part:
                k, v = part.split('=', 1)
                fields[k.strip()] = v.strip()
        pos = POS.get(fields.get('pos', '').upper())
        link = re.search(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', fields.get('name', ''))
        if not pos or not link:
            continue
        players.append({
            'wiki': link.group(1).strip(),
            'en': (link.group(2) or re.sub(r'\s*\(.*\)$', '', link.group(1))).strip(),
            'position': pos,
            'nat': fields.get('nat', '').upper(),
        })
    return players


def ru_name(ru_title, fallback):
    if not ru_title:
        return fallback
    name = re.sub(r'\s*\(.*\)$', '', ru_title)
    if ', ' in name:
        last, first = name.split(', ', 1)
        name = f'{first} {last}'
    return name


def enrich(players):
    """Русское название статьи и файл фото — пачками по 50."""
    for i in range(0, len(players), 50):
        chunk = players[i:i + 50]
        data = get(EN_API, {
            'action': 'query', 'titles': '|'.join(p['wiki'] for p in chunk), 'redirects': 1,
            'prop': 'langlinks|pageimages', 'lllang': 'ru', 'lllimit': 'max',
            'piprop': 'name|thumbnail', 'pithumbsize': 300, 'pilicense': 'free',
        })['query']
        mapping = {}
        for key in ('normalized', 'redirects'):
            for r in data.get(key, []):
                mapping[r['from']] = r['to']
        pages = {p['title']: p for p in data.get('pages', [])}
        for p in chunk:
            t = p['wiki']
            while t in mapping:
                t = mapping[t]
            page = pages.get(t, {})
            ll = page.get('langlinks') or []
            p['ru_title'] = ll[0]['title'] if ll else None
            p['file'] = page.get('pageimage')
            p['thumb'] = page.get('thumbnail', {}).get('source')
        time.sleep(1)


def slug(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def download_photos(players):
    os.makedirs(IMG_DIR, exist_ok=True)
    credits = {}
    todo = [p for p in players if p.get('thumb')]
    # Авторы и лицензии файлов
    files = sorted({p['file'] for p in todo})
    for i in range(0, len(files), 50):
        data = get(EN_API, {'action': 'query', 'titles': '|'.join('File:' + f for f in files[i:i + 50]),
                            'prop': 'imageinfo', 'iiprop': 'extmetadata|url'})['query']
        for page in data.get('pages', []):
            info = (page.get('imageinfo') or [{}])[0]
            meta = info.get('extmetadata', {})
            artist = re.sub(r'<[^>]+>', '', meta.get('Artist', {}).get('value', '')).strip()
            credits[page['title'].split(':', 1)[1].replace(' ', '_')] = {
                'artist': artist or 'неизвестен',
                'license': meta.get('LicenseShortName', {}).get('value', ''),
                'url': info.get('descriptionurl', ''),
            }
        time.sleep(1)

    for n, p in enumerate(todo, 1):
        ext = os.path.splitext(p['thumb'])[1].lower() or '.jpg'
        if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
            ext = '.jpg'
        path = f'{IMG_DIR}/{slug(p["wiki"])}{ext}'
        if not os.path.exists(path):
            with open(path, 'wb') as f:
                f.write(get(p['thumb'], raw=True))
            time.sleep(0.5)
            print(f'  [{n}/{len(todo)}] {path}', flush=True)
        p['photo'] = path

    # Фото игроков, которых больше нет в базе
    used = {os.path.basename(p['photo']) for p in todo}
    for name in os.listdir(IMG_DIR):
        if name != 'CREDITS.md' and name not in used:
            os.remove(f'{IMG_DIR}/{name}')

    with open(f'{IMG_DIR}/CREDITS.md', 'w', encoding='utf-8') as f:
        f.write('# Фото футболистов\n\nВсе фото — с Wikimedia Commons, под свободными лицензиями.\n\n')
        f.write('| Футболист | Автор | Лицензия | Источник |\n|---|---|---|---|\n')
        for p in sorted(todo, key=lambda x: x['name']):
            c = credits.get(p['file'].replace(' ', '_'), {})
            artist = c.get('artist', '').replace('|', '/').replace('\n', ' ')
            f.write(f"| {p['name']} | {artist} | {c.get('license', '')} | {c.get('url', '')} |\n")


def main():
    ratings = {}
    if os.path.exists(RATINGS):
        with open(RATINGS, encoding='utf-8') as f:
            ratings = json.load(f)

    players, seen = [], set()
    for title, club_ru in CLUBS.items():
        squad = parse_players(squad_section(title))
        print(f'{club_ru:<20} {len(squad)} игроков', flush=True)
        for p in squad:
            if p['wiki'] in seen:
                continue
            seen.add(p['wiki'])
            p['club'] = club_ru
            players.append(p)
        time.sleep(1)

    enrich(players)
    # Без статьи в русской Википедии — обычно юниоры из заявки, их выкидываем
    players = [p for p in players if p['ru_title']]
    for p in players:
        p['name'] = NAME_OVERRIDES.get(p['en']) or ru_name(p['ru_title'], p['en'])
        p['country'] = COUNTRIES.get(p['nat'], p['nat'])
        p['rating'] = ratings.get(p['en'], DEFAULT_RATING)

    if '--photos' in sys.argv:
        download_photos(players)

    out = [{k: p[k] for k in ('name', 'position', 'club', 'country', 'rating', 'photo', 'en') if p.get(k) is not None}
           for p in players]
    with open(DB, 'w', encoding='utf-8') as f:
        f.write('[\n' + ',\n'.join('  ' + json.dumps(p, ensure_ascii=False) for p in out) + '\n]\n')

    counts = {pos: sum(p['position'] == pos for p in out) for pos in POS.values()}
    print(f'\nВсего: {len(out)} {counts}')
    print('Без русского имени:', [p['en'] for p in players if not p['ru_title']])
    print('Без фото:', sum(1 for p in players if not p.get('thumb')))
    print('Неизвестные страны:', sorted({p['nat'] for p in players if p['nat'] not in COUNTRIES}))


if __name__ == '__main__':
    main()
