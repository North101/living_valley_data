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

  resource_id = '/'.join(get_nav_parents(tree))
  items = list(list_nav_items(tree))
  yield url, resource_id

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
  resource_id = '/'.join(get_nav_parents(tree))
  items = list(list_nav_items(tree))
  yield title, url, resource_id, items, content

  for item in items:
    item_url = item[2]
    yield from scrape_page(session, base_url, item_url)


def parse_element(e: Any, urls: dict[str, str], icon_color: str | None):
  tag: str = e.tag
  classes = list(e.classes)
  TAG_CLASSES.setdefault(tag, set()).update(classes)

  resource_id: str | None = None
  anchor: str | None = None
  url: str | None = None
  if tag == 'a':
    url = clean_url(e.get('href'))
    TAG_URLS.add(url)
    resource_id, anchor = rewrite_url(url, urls)
  elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
    anchor = (
        e.get('id')
        if CLASS_ANCHOR in classes else
        None
    )

  color = get_color_for_class(
      classes,
      colors=CSS_TEXT_COLORS,
  )
  highlight_color = get_color_for_class(
      classes,
      CSS_HIGHLIGHT_COLORS,
  )

  items = list(parse_element_items(
      e,
      urls,
      get_color_for_class(
          classes,
          CSS_ICON_COLORS,
      ) or icon_color,
  ))

  data = {
      'type': tag,
      'items': items,
  }
  if tag == 'a':
    data.update({
        'link': {
          'id': resource_id,
          'anchor': anchor,
          'url': url,
        },
    })
  elif anchor:
    data.update({
        'anchor': anchor,
    })

  if color:
    data.update({
        'color': color,
    })

  if highlight_color:
    data.update({
        'highlight_color': highlight_color,
    })
  
  # if 'button' in classes:
  #   data.update({
  #     'button': True,
  #   })

  return data


def parse_element_items(parent: Any, urls: dict[str, str], icon_color: str | None):
  if parent.text and parent.text.strip():
    yield from process_text(parent.text.strip(), icon_color)

  for child in parent:
    yield parse_element(child, urls, icon_color)

    if child.tail and child.tail.strip():
      yield from process_text(child.tail.strip(), icon_color)


def process_text(text: str, icon_color: str | None):
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
          'color': icon_color,
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


def get_lookup_group(resource_id: str):
  parts = resource_id.split('/')
  if parts[0] in ('campaign_guides', 'one_day_missions') and len(parts) > 1:
    return '/'.join(parts[:2])
  if parts[0] == 'rules_glossary':
    return parts[0]
  return None


def get_lookup(resource_id: str, title: str) -> tuple[None, None] | tuple[str, None] | tuple[str, str]:
  lookup_group = get_lookup_group(resource_id)
  if not lookup_group:
    return None, None

  id_parts = resource_id.split('/')
  lookup_parts = lookup_group.split('/')
  if lookup_parts[0] == 'campaign_guides' and len(id_parts) > 2 and (guide_entry := get_guide_entry(title)):
    return lookup_group, guide_entry
  if lookup_parts[0] == 'one_day_missions' and len(id_parts) > 2:
    return lookup_group, id_parts[-1]
  if lookup_parts[0] == 'rules_glossary' and len(id_parts) > 1:
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
        url: resource_id
        for page_url in page_urls
        for url, resource_id in scrape_urls(session, base_url, page_url)
    }
    for page_url in page_urls:
      sections = scrape_page(session, base_url, page_url)
      for title, url, resource_id, items, data in sections:
        file = output_dir / f'{resource_id}.json'
        content = (
            remove_content_title(list(parse_element_items(data, urls, None)))
            if data is not None else
            None
        )

        lookup_group, lookup_id = get_lookup(resource_id, title)
        file.parent.mkdir(exist_ok=True, parents=True)
        with file.open('w') as f:
          json.dump({
              'id': resource_id,
              'lookup_group': lookup_group,
              'lookup_id': lookup_id,
              'title': title,
              'content': content,
              'items': [
                  '/'.join((resource_id, item_id))
                  for item_id, _, _ in items
              ],
              'url': url,
          }, f, indent=2)

  log_dir = pathlib.Path('.', 'log')
  log_dir.mkdir(exist_ok=True, parents=True)

  with (log_dir / 'tags.json').open('w') as f:
    json.dump({
        key: sorted(value)
        for key, value in sorted(TAG_CLASSES.items(), key=lambda x: x[0])
    }, f, indent=2)

  with (log_dir / 'urls.json').open('w') as f:
    json.dump(sorted(TAG_URLS), f, indent=2)
