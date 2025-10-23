import json
import pathlib
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from lxml import html

HTML_PARSER = html.HTMLParser(remove_blank_text=True, remove_comments=True)


def parse_html(content: str):
  return html.fromstring(content, parser=HTML_PARSER)  # type: ignore


def clean_url(url: str):
  return url.rstrip('/')


def to_id(title: str):
  return ''.join((
      c
      for c in iter_id(title)
  )).strip('_')


def iter_id(title: str):
  wasalnum = False
  for c in title:
    if c.isalnum():
      wasalnum = True
      yield c.lower()
    elif wasalnum and (c.isspace() or c in ('.', '-', '_')):
      wasalnum = False
      yield '_'


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


def get_color_for_class(classes: list[str], colors: dict[str, str]):
  return next((
      color
      for css_class, color in colors.items()
      if css_class in classes
  ), None)


def write_resource(
    path: pathlib.Path,
    resource_id: str,
    title: str,
    content: Any | None,
    links: list[dict[str, str]],
    lookup: list[dict[str, str]],
    url: str,
):
  write_json(path, {
      'id': resource_id,
      'title': title,
      'content': content,
      'links': links,
      'lookup': lookup if lookup else None,
      'url': url,
  })


def write_json(path: pathlib.Path, obj: Any):
  path.parent.mkdir(exist_ok=True, parents=True)
  with path.open('w') as f:
    json.dump(obj, f, indent=2)
