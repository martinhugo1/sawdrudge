"""Live editorial page mirror with replaceable branding.

Before public deployment, check the source publisher's terms and permissions.
"""
import os
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, Response, send_from_directory

app = Flask(__name__)
SOURCE = os.getenv('SOURCE_URL', 'https://www.drudgereport.com/')
REFRESH_SECONDS = max(30, int(os.getenv('REFRESH_SECONDS', '180')))
LOGO_URL = '/static/your-logo.png'
HERO_URL = '/static/your-main-image.jpg'
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; BrandMirror/1.0; +contact-site-operator)', 'Accept': 'text/html,application/xhtml+xml'}
_cache = {'until': 0, 'html': None}


def abs_urls(soup, base):
    for node in soup.find_all(True):
        for attr in ('href', 'src', 'poster', 'action'):
            if not node.has_attr(attr):
                continue
            value = node[attr].strip()
            if not value or value.startswith(('#', 'data:', 'javascript:', 'mailto:', 'tel:')):
                continue
            node[attr] = urljoin(base, value)
        if node.has_attr('srcset'):
            parts = []
            for item in node['srcset'].split(','):
                pieces = item.strip().split()
                if pieces:
                    pieces[0] = urljoin(base, pieces[0])
                    parts.append(' '.join(pieces))
            node['srcset'] = ', '.join(parts)


def replace_masthead(soup):
    # Prefer replacing branded masthead imagery rather than a news photo.
    for img in soup.find_all('img'):
        attrs = ' '.join(str(img.get(k, '')) for k in ('src', 'alt', 'id', 'class')).lower()
        if 'logo' in attrs or 'masthead' in attrs or 'drudge' in attrs or 'eproof.drudgereport.com' in attrs:
            img['src'] = LOGO_URL
            img['srcset'] = ''
            img['alt'] = 'Your site logo'
            img['style'] = (img.get('style', '') + ';display:block;max-width:min(95vw,700px);width:100%;height:auto;object-fit:contain;margin:0 auto;').strip(';')
            return img
    # Some editions use an old-fashioned text masthead.
    for text in soup.find_all(string=re.compile(r'DRUDGE\s+REPORT', re.I)):
        parent = text.parent
        if parent and parent.name not in ('script', 'style', 'title'):
            if parent.name in ('a', 'b', 'strong', 'font', 'center', 'div'):
                logo = soup.new_tag('img', src=LOGO_URL, alt='Your site logo')
                logo['style'] = 'display:block;max-width:min(95vw,700px);width:100%;height:auto;object-fit:contain;margin:0 auto'
                parent.clear()
                parent.append(logo)
                return logo
    # Fallback: introduce branded heading without deleting news content.
    logo = soup.new_tag('img', src=LOGO_URL, alt='Your site logo')
    logo['style'] = 'display:block;max-width:min(95vw,700px);width:100%;height:auto;object-fit:contain;margin:14px auto'
    (soup.body or soup).insert(0, logo)
    return logo


def replace_main_image(soup, masthead):
    # Select the first editorial-sized image, skipping logos, trackers, and tiny icons.
    for img in soup.find_all('img'):
        if img is masthead:
            continue
        attrs = ' '.join(str(img.get(k, '')) for k in ('src', 'alt', 'id', 'class')).lower()
        if any(x in attrs for x in ('logo', 'masthead', 'drudge', 'pixel', 'tracker', 'icon', 'badge', 'button', 'spacer')):
            continue
        try:
            w, h = int(img.get('width', 0)), int(img.get('height', 0))
        except (ValueError, TypeError):
            w, h = 0, 0
        if (w and w < 100) or (h and h < 70):
            continue

        img['src'] = HERO_URL
        img.attrs.pop('srcset', None)
        img['alt'] = 'Custom main image'
        existing = img.get('style', '').rstrip(';')
        img['style'] = (existing + ';display:block;max-width:100%;width:auto;height:auto;object-fit:contain;').strip(';')
        return True

    # Fallback: if no qualifying image is found, inject the custom hero below the masthead.
    hero = soup.new_tag('img', src=HERO_URL, alt='Custom main image')
    hero['style'] = 'display:block;max-width:100%;width:auto;height:auto;object-fit:contain;margin:10px auto;'
    anchor = masthead
    if anchor and getattr(anchor, 'parent', None):
        anchor.insert_after(hero)
    elif soup.body:
        soup.body.insert(1, hero)
    else:
        soup.insert(0, hero)
    return True


def build_page(raw):
    soup = BeautifulSoup(raw, 'html.parser')
    if not soup.html:
        raise ValueError('Upstream response was not an HTML page.')
    abs_urls(soup, SOURCE)
    # Prevent mirroring upstream analytics, advertisements, or scripts that might
    # overwrite the substituted assets. Editorial content and links remain.
    for tag in soup.find_all(['script', 'iframe', 'noscript']):
        tag.decompose()
    for meta in soup.find_all('meta', attrs={'http-equiv': re.compile(r'refresh', re.I)}):
        meta.decompose()
    if soup.head:
        title = soup.head.find('title')
        if title:
            title.string = 'SAWDRUDGE'
        style = soup.new_tag('style')
        style.string = '@media(max-width:700px){img{max-width:100%;height:auto}body{overflow-wrap:anywhere}}'
        soup.head.append(style)
    masthead = replace_masthead(soup)
    replace_main_image(soup, masthead)
    return str(soup)


@app.get('/')
def index():
    now = time.time()
    if _cache['html'] and now < _cache['until']:
        return Response(_cache['html'], mimetype='text/html')
    try:
        result = requests.get(SOURCE, headers=HEADERS, timeout=15)
        result.raise_for_status()
        result.encoding = result.apparent_encoding or 'utf-8'
        markup = build_page(result.text)
        _cache.update(html=markup, until=now + REFRESH_SECONDS)
        return Response(markup, mimetype='text/html')
    except (requests.RequestException, ValueError) as err:
        if _cache['html']:
            return Response(_cache['html'], mimetype='text/html', headers={'X-Mirror-Status': 'stale'})
        return Response('Upstream site temporarily unavailable. Check SOURCE_URL and server logs.', status=502, mimetype='text/plain')


@app.get('/health')
def health():
    return {'status': 'ok', 'cached': bool(_cache['html']), 'refresh_seconds': REFRESH_SECONDS}


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '8000')))
