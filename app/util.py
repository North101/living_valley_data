import pathlib
from urllib.parse import urljoin, urlparse, urlunparse
import re

import requests
from lxml import html

HTML_PARSER = html.HTMLParser(remove_blank_text=True, remove_comments=True)


def parse_html(content: str):
  return html.fromstring(content, parser=HTML_PARSER)


def clean_url(url: str):
  return url.rstrip('/')


def to_id(title: str):
  return ''.join((
      c
      for c in title.lower()
      if c.isalnum() or c.isspace() or c in ['.', '-']
  )).replace(' ', '_').replace('.', '_').replace('-', '_').replace('__', '_')


def get_content(session: requests.Session, base_url: str, url: str):
  file = pathlib.Path(f'./cache/{clean_url(url)}.html')
  if file.exists():
    return file.read_text('utf8')

  content = session.get(urljoin(base_url, url), timeout=30).text
  file.parent.mkdir(exist_ok=True, parents=True)
  file.write_text(content, 'utf8')

  return content


def rewrite_url(base_url: str, url: str, urls: dict[str, str]):
  scheme, netloc, path, params, query, fragment = urlparse(url)
  path = urls.get(path, '')
  if not path and not fragment:
    if url.startswith('/'):
      return urljoin(base_url, url)

    return url

  return urlunparse((
      scheme,
      netloc,
      path,
      params,
      query,
      fragment,
  ))


def get_guide_entry(title: str) -> str | None:
  match = re.match(r'^(\d+)\.(\d+)?', title)
  if not match:
    return None

  main, sub = match.groups()
  if sub:
    return f'{main}.{sub}'
  return main


def get_color_for_class(classes: list[str], colors: dict[str, str]):
  return next((
      color
      for css_class, color in colors.items()
      if css_class in classes
  ), None)
