import json
import pathlib
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from .constants import *
from .util import *

TAG_CLASSES: dict[str, set[str]] = {}
TAG_URLS = set[str]()
TAG_ICONS = set[str]()


def get_nav_parents(e: Any):
  for item in e.xpath(NAV_PARENT_URLS):
    yield from next_nav_parent(item)


def next_nav_parent(e: Any):
  for item in e.xpath('./parent::div/parent::ul/parent::li/div/a[1]'):
    yield from next_nav_parent(item)
  for item in e.xpath('./parent::ul/parent::li/div/a[1]'):
    yield from next_nav_parent(item)
  yield to_id(e.text)


def list_nav_items(e: Any):
  for item in e.xpath(NAV_ITEM_URLS):
    yield to_id(item.text), item.text, clean_url(item.get('href'))


def scrape_urls(session: requests.Session, base_url: str, url: str):
  data = get_content(session, base_url, url)
  if not data:
    print(url)
  tree = parse_html(data)

  page_id = '/'.join(get_nav_parents(tree))
  items = list(list_nav_items(tree))
  yield url, page_id

  for item in items:
    item_url = item[2]
    yield from scrape_urls(session, base_url, item_url)


def scrape_page(session: requests.Session, base_url: str, url: str):
  data = get_content(session, base_url, url)
  if not data:
    print(url)
  tree = parse_html(data)

  title = next(iter(tree.xpath('//header/h1//text()')), None)
  if title is None:
    title = next(iter(tree.xpath('//article/div/h1//text()')))
    content: Any = next(iter(tree.xpath(SECTION_MARKDOWN)), None)
  else:
    content = None
  page_id = '/'.join(get_nav_parents(tree))
  items = list(list_nav_items(tree))
  yield title, url, page_id, items, content

  for item in items:
    item_url = item[2]
    yield from scrape_page(session, base_url, item_url)


def parse_section(parent: Any, urls: dict[str, str]):
  return [
      parse_element(child, urls)
      for child in parent
  ]


def parse_element(e: Any, urls: dict[str, str]):
  tag: str = e.tag
  classes = list(e.classes)

  TAG_CLASSES.setdefault(tag, set()).update(classes)
  data = {
      'type': tag,
      'items': list(parse_element_items(e, urls)),
  }
  if tag == 'a':
    url: str = clean_url(e.get('href'))
    TAG_URLS.add(url)
    page_id, anchor = rewrite_url(url, urls)
    data.update({
        'id': page_id,
        'anchor': anchor,
        'url': url,
    })
  elif tag == 'span':
    for css_class, color in CSS_ICON_COLORS.items():
      if css_class in classes:
        TAG_ICONS.update((
            i
            for i in e.text
            if not i.isascii()
        ))
        data.update({
            'icon_color': color,
        })

  for css_class, color in CSS_TEXT_COLORS.items():
    if css_class in classes:
      data.update({
          'color': color,
      })

  for css_class, color in CSS_HIGHLIGHT_COLORS.items():
    if css_class in classes:
      data.update({
          'highlight_color': color,
      })

  if CLASS_ANCHOR in classes:
    data.update({
        'anchor': e.get('id'),
    })

  return data


def parse_element_items(parent: Any, urls: dict[str, str]):
  if parent.text and parent.text.strip():
    yield from process_text(parent.text.strip())

  for child in parent:
    yield parse_element(child, urls)

    if child.tail and child.tail.strip():
      yield from process_text(child.tail.strip())


def process_text(text: str):
  start = 0
  i = 0
  for i, c in enumerate(iterable=text):
    if c in RANGER_ICON_NAMES:
      if i > start:
        yield {
            'type': 'text',
            'text': text[start:i+1],
        }
      yield {
          'type': 'icon',
          'icon': RANGER_ICON_NAMES[c],
      }
      start = i + 1

  if i > start:
    yield {
        'type': 'text',
        'text': text[start:i+1],
    }


def remove_content_title(data: list):
  assert data[0]['type'] == 'h1'
  return data[1:]


def get_lookup_group(page_id: str):
  parts = page_id.split('/')
  if parts[0] in ('campaign_guides', 'one_day_missions') and len(parts) > 1:
    return '/'.join(parts[:2])
  elif parts[0] == 'rules_glossary':
    return parts[0]
  return None


def get_lookup(page_id: str, title: str) -> tuple[None, None] | tuple[str, None] | tuple[str, str]:
  lookup_group = get_lookup_group(page_id)
  if not lookup_group:
    return None, None

  id_parts = page_id.split('/')
  lookup_parts = lookup_group.split('/')
  if lookup_parts[0] == 'campaign_guides' and len(id_parts) > 2 and (guide_entry := get_guide_entry(title)):
    return lookup_group, guide_entry
  elif lookup_parts[0] == 'one_day_missions' and len(id_parts) > 2:
    return lookup_group, id_parts[-1]
  elif lookup_parts[0] == 'rules_glossary' and len(id_parts) > 1:
    return lookup_group, id_parts[-1]
  return lookup_group, None


def main(base_url: str, page_urls: list[str]):
  output_dir = pathlib.Path('.', 'output')
  with requests.Session() as session:
    session.mount('https://', HTTPAdapter(max_retries=Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
    )))
    session.headers = {
        'user-agent': USER_AGENT,
    }

    urls = {
        url: page_id
        for page_url in page_urls
        for url, page_id in scrape_urls(session, base_url, page_url)
    }
    for page_url in page_urls:
      sections = scrape_page(session, base_url, page_url)
      for title, url, page_id, items, data in sections:
        file = output_dir / f'{page_id}.json'
        content = (
            remove_content_title(parse_section(data, urls))
            if data is not None else
            None
        )

        lookup_group, lookup_id = get_lookup(page_id, title)
        file.parent.mkdir(exist_ok=True, parents=True)
        with file.open('w') as f:
          json.dump({
              'id': page_id,
              'lookup_group': lookup_group,
              'lookup_id': lookup_id,
              'title': title,
              'content': content,
              'items': [
                  '/'.join((page_id, item_id))
                  for item_id, _, _ in items
              ],
              'url': url,
          }, f, indent=2)

  log_dir = pathlib.Path('.', 'log')
  log_dir.mkdir(exist_ok=True, parents=True)

  with (log_dir / 'tags.json').open('w') as f:
    json.dump({
        key: sorted(value)
        for key, value in TAG_CLASSES.items()
    }, f, indent=2)

  with (log_dir / 'urls.json').open('w') as f:
    json.dump(sorted(TAG_URLS), f, indent=2)

  with (log_dir / 'icons.json').open('w') as f:
    json.dump(sorted(TAG_ICONS), f, indent=2)
