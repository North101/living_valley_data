import json
import pathlib
from shutil import rmtree
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from .constants import *
from .util import *

TAG_CLASSES = dict[str, set[str]]()
TAG_ITEMS_TYPES = dict[str, set[str]]()
TAG_URLS = set[str]()
TAG_ICONS = dict[str, str | None]()
TAG_ATTRIBUTES = dict[str, set[str]]()


def get_nav_parents(e: Any):
  for item in e.xpath(NAV_PARENT_URLS):
    yield from next_nav_parent(item)


def next_nav_parent(e: Any):
  for item in e.xpath(NEXT_NAV_PARENT):
    yield from next_nav_parent(item)
  yield to_id(e.text)


def list_nav_items(e: Any):
  for item in e.xpath(NAV_ITEM_URLS):
    yield to_id(item.text), item.text, clean_url(item.get('href'))


def scrape_page(session: requests.Session, base_url: str, url: str):
  data = get_content(session, base_url, url)
  if not data:
    print(url)
  tree = parse_html(data)

  title = next(iter(tree.xpath(PAGE_TITLE)))
  resource_id = '/'.join(get_nav_parents(tree))
  items = list(list_nav_items(tree))
  content: Any = next(iter(tree.xpath(SECTION_MARKDOWN)), None)
  yield url, resource_id, title, items, content

  for item in items:
    item_url = item[2]
    yield from scrape_page(session, base_url, item_url)


def parse_element(base_url: str, e: Any, urls: dict[str, str], icon_color: str | None):
  tag: str = e.tag
  tag = REPLACE_TAG.get(tag, tag)

  classes = list(e.classes)

  if tag == 'a' and 'button' in classes:
    tag = 'button'

  url: str | None = None
  if tag in ('a', 'button'):
    url = clean_url(e.get('href'))
    TAG_URLS.add(url)
    url = rewrite_url(base_url, url, urls)

  TAG_CLASSES.setdefault(tag, set()).update(classes)
  if tag in ('h1', 'h2', 'choice', 'branch', 'imgfooter'):
    anchor = (
        e.get('id')
        if CLASS_ANCHOR in classes else
        None
    )
  else:
    anchor = None

  color = get_color_for_class(
      classes,
      colors=CSS_TEXT_COLORS,
  )
  highlight_color = get_color_for_class(
      classes,
      CSS_HIGHLIGHT_COLORS,
  )

  items = list(parse_element_items(
      base_url,
      e,
      urls,
      get_color_for_class(
          classes,
          CSS_ICON_COLORS,
      ) or icon_color,
  ))
  # Change <p><i><p ...> to <p ...><i>
  if tag == 'p' and len(items) == 1 and (item := items[0]):
    if item['type'] in ('b', 'i', 'span'):
      if item['items'][-1] == {'type': 'text', 'text': ' '}:
        item['items'].pop()
      if len(item['items']) == 1 and (subitem := item['items'][0]) and subitem['type'] == 'p':
        color = subitem.get('color')
        item['items'] = subitem['items']

  # Remove unnessesary spans
  if tag in ('p', 'span', 'b', 'i'):
    if items and len(items) == 1 and (item := items[0]) and item['type'] == 'span':
      return {
          **item,
          'type': tag,
          'color': color or item.get('color'),
      }

  if tag in ('branch', 'choice'):
    if len(items) == 1 and items[0]['type'] == 'text':
      items[0]['text'] = items[0]['text'].upper()

  TAG_ITEMS_TYPES.setdefault(tag, set()).update((
      item['type']
      for item in items
  ))

  data: dict[str, Any] = {
      'type': tag,
  }
  if tag not in ('hr', 'br', 'img'):
    data.update({
        'items': items,
    })

  if tag in ('a', 'button'):
    data.update({
        'href': url,
    })
  elif tag == 'img':
    src = e.get('src')
    if src.startswith('/'):
      src = urljoin(base_url, src)

    data.update({
        'src': src,
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
        'type': 'highlight',
        'highlight': highlight_color,
    })

  return data


def parse_element_items(base_url: str, parent: Any, urls: dict[str, str], icon_color: str | None):
  if parent.text and parent.text:
    yield from process_text(parent.text, icon_color)

  for child in parent:
    element = parse_element(base_url, child, urls, icon_color)
    if not (element['type'] == 'a' and element['items'] == [{'type': 'text', 'text': '\u200b'}]):
      yield element

    if child.tail and child.tail:
      yield from process_text(child.tail, icon_color)


def process_text(text: str, icon_color: str | None):
  start = 0
  i = 0
  for i, c in enumerate(iterable=text):
    code = ord(c)
    if 0xE000 <= code <= 0xF8FF:
      TAG_ICONS[c] = RANGER_ICON_NAMES.get(c)

    if c in RANGER_ICON_NAMES:
      if i > start:
        yield {
            'type': 'text',
            'text': text[start:i+1].replace('\n', ' '),
        }
      yield {
          'type': 'span',
          'color': icon_color,
          'items': [{
              'type': 'icon',
              'icon': RANGER_ICON_NAMES[c],
              'items': [{
                  'type': 'text',
                  'text': '&nbsp;',
              }]
          }],
      }
      start = i + 1

  if i >= start:
    yield {
        'type': 'text',
        'text': text[start:i+1].replace('\n', ' '),
    }


def remove_content_title(data: list):
  assert data[0]['type'] == 'title'
  return data[1:]


def get_lookup_group(resource_id: str):
  parts = resource_id.split('/')
  if parts[0] in ('campaign_guides', 'one_day_missions') and len(parts) > 1:
    return '/'.join(parts[:2])
  if parts[0] == 'rules_glossary':
    return parts[0]
  return None


def content_to_html(resource_id: str, content: list[dict[str, Any]] | None):
  if not content:
    return ''

  return ''.join((
      content_item_to_html(resource_id, item)
      for item in content
  ))


def content_item_to_html(resource_id: str, content: dict[str, Any]):
  tag = content['type']
  if tag == 'text':
    return content['text']

  items = content.get('items')
  attributes = {}

  color = content.get('color')
  if color:
    attributes['color'] = color
  # Remove unnessesary spans
  elif tag == 'span':
    return content_to_html(resource_id, items)

  if tag == 'icon':
    attributes['icon'] = content.get('icon')
    # return f'[{icon}]'

  if tag == 'highlight':
    attributes['highlight'] = content.get('highlight')

  anchor = content.get('anchor')
  if anchor:
    attributes['id'] = anchor

  href: str | None = content.get('href')
  if href:
    if href.startswith(f'{resource_id}#'):
      href = href.removeprefix(resource_id)
    attributes['href'] = href

  if tag == 'img':
    attributes['src'] = content.get('src')

  TAG_ATTRIBUTES.setdefault(tag, set()).update(attributes)
  if attributes:
    attributes = f' {' '.join(f'{k}="{v}"' for k, v in attributes.items())}'
  else:
    attributes = ''

  if tag in ('br', 'hr', 'img'):
    return f'<{tag}{attributes}>'

  return f'<{tag}{attributes}>{content_to_html(resource_id, items)}</{tag}>'


def main(base_url: str, page_urls: list[str]):
  output_dir = pathlib.Path('.', 'output')
  rmtree(output_dir)

  with requests.Session() as session:
    session.mount('https://', HTTPAdapter(max_retries=Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
    )))
    session.headers = {
        'user-agent': USER_AGENT,
    }

    urls = dict[str, str]()
    titles = dict[str, str]()
    lookup = dict[str, list[dict[str, str]]]()
    for page_url in page_urls:
      for url, resource_id, title, _, _ in scrape_page(session, base_url, page_url):
        urls[url] = resource_id
        titles[url] = title

        lookup_group = get_lookup_group(resource_id)
        if lookup_group and lookup_group != resource_id:
          lookup.setdefault(lookup_group, []).append({
              'id': resource_id,
              'title': title,
          })

    for page_url in page_urls:
      for url, resource_id, title, items, data in scrape_page(session, base_url, page_url):
        file = output_dir / 'data' / f'{resource_id}.json'
        content = (
            remove_content_title(list(parse_element_items(
                base_url,
                data,
                urls,
                None,
            )))
            if data is not None else
            None
        )
        content = content_to_html(
            resource_id,
            content,
        ) if content else None

        lookup_group = get_lookup_group(resource_id)
        file.parent.mkdir(exist_ok=True, parents=True)
        with file.open('w') as f:
          json.dump({
              'id': resource_id,
              'title': title,
              'content': content,
              'links': [
                  {
                      'id': '/'.join((resource_id, item_id)),
                      'title': item_title,
                  }
                  for item_id, item_title, _ in items
              ],
              'lookup': (
                  lookup[lookup_group]
                  if lookup_group and lookup_group == resource_id else
                  None
              ),
              'url': clean_url(url),
          }, f, indent=2)

    file = output_dir / 'data.json'
    file.parent.mkdir(exist_ok=True, parents=True)
    with file.open('w') as f:
      json.dump({
          'id': '',
          'title': 'The Living Valley',
          'content': None,
          'links': [
              {
                'id': urls[page_url],
                'title': titles[page_url],
              }
              for page_url in page_urls
          ],
          'lookup': None,
          'url': base_url,
      }, f, indent=2)

  log_dir = pathlib.Path('.', 'log')
  rmtree(log_dir)
  log_dir.mkdir(exist_ok=True, parents=True)

  with (log_dir / 'tags.json').open('w') as f:
    json.dump({
        key: sorted(value)
        for key, value in sorted(TAG_ITEMS_TYPES.items(), key=lambda x: x[0])
    }, f, indent=2)

  with (log_dir / 'classes.json').open('w') as f:
    json.dump({
        key: sorted(value)
        for key, value in sorted(TAG_CLASSES.items(), key=lambda x: x[0])
    }, f, indent=2)

  with (log_dir / 'urls.json').open('w') as f:
    json.dump(sorted(TAG_URLS), f, indent=2)

  with (log_dir / 'icons.json').open('w') as f:
    json.dump(dict(sorted(TAG_ICONS.items(), key=lambda x: x[0])), f, indent=2)

  with (log_dir / 'attributes.json').open('w') as f:
    json.dump({
        key: sorted(value)
        for key, value in sorted(TAG_ATTRIBUTES.items(), key=lambda x: x[0])
    }, f, indent=2)
