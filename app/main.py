import enum
import html
import pathlib
from collections.abc import Sequence
from dataclasses import asdict, replace
from shutil import rmtree
from typing import Generator
from urllib.parse import urljoin

import requests
from lxml.html import HtmlElement
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from . import constants
from . import tags
from . import util


class IconType(enum.StrEnum):
  TEXT = enum.auto()
  ELEMENT = enum.auto()


class ContentType(enum.StrEnum):
  XHTML = enum.auto()
  JSON = enum.auto()


class Scraper:
  TAG_CLASSES = dict[str, set[str]]()
  TAG_ITEMS_TYPES = dict[str, set[str]]()
  TAG_URLS = set[str]()
  TAG_ICONS = dict[str, str | None]()

  def __init__(
      self,
      base_url: str,
      page_urls: list[str],
      icon_type: IconType,
      content_type: ContentType,
  ):
    self.base_url = base_url
    self.page_urls = page_urls

    self.session = requests.Session()
    self.session.mount('https://', HTTPAdapter(max_retries=Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
    )))
    self.session.headers = {
        'user-agent': constants.USER_AGENT,
    }
    self.output_dir = pathlib.Path('.', 'output')
    self.log_dir = pathlib.Path('.', 'log')

    self.icon_type = icon_type
    self.content_type = content_type

  def get_nav_parents(self, e: HtmlElement) -> Generator[str]:
    for item in e.xpath(constants.NAV_PARENT_URLS):
      yield from self.next_nav_parent(item)

  def next_nav_parent(self, e: HtmlElement) -> Generator[str]:
    for item in e.xpath(constants.NEXT_NAV_PARENT):
      yield from self.next_nav_parent(item)
    yield util.to_id(e.text or '')

  def list_nav_items(self, e: HtmlElement) -> Generator[tuple[str, str, str]]:
    for item in e.xpath(constants.NAV_ITEM_URLS):
      yield util.to_id(item.text), str(item.text), util.clean_url(item.get('href'))

  def scrape_page(self, url: str):
    data = util.get_content(self.session, self.base_url, url)
    if not data:
      print(url)
    tree = util.parse_html(data)

    title = str(next(iter(tree.xpath(constants.PAGE_TITLE))))
    resource_id = '/'.join(self.get_nav_parents(tree))
    items = list(self.list_nav_items(tree))
    content = next(iter(tree.xpath(constants.SECTION_MARKDOWN)), None)
    yield url, resource_id, title, items, content

    for item in items:
      yield from self.scrape_page(item[2])

  def parse_element(self, e: HtmlElement, urls: dict[str, str], icon_color: str | None) -> Generator[tags.Tag]:
    tag = str(e.tag)
    tag = constants.REPLACE_TAG.get(tag, tag)

    classes = list(e.classes)

    if tag == 'a' and 'button' in classes:
      tag = 'button'

    self.TAG_CLASSES.setdefault(tag, set()).update(classes)

    color = util.get_color_for_class(
        classes,
        colors=constants.CSS_TEXT_COLORS,
    )

    items: list[tags.Tag] = list(self.parse_element_items(
        e,
        urls,
        util.get_color_for_class(
            classes,
            constants.CSS_ICON_COLORS,
        ) or icon_color,
    ))

    # Remove unnessesary spans
    if tag == 'span' and not color:
      yield from items
      return

    # Cleanup paragraphs
    if tag == 'p' and len(items) == 1:
      item = items[0]
      if isinstance(item, tags.TagFormattedText):
        # Remove trailing spaces
        if item.items and item.items[-1] == tags.TagText('text', ' '):
          item.items.pop()

    if tag in ('p', 'b', 'i', 'span'):
      if items and len(items) == 1 and (item := items[0]) and isinstance(item, tags.TagFormattedText):
        # Bring colors to the top
        color = item.color or color
        item.color = None

        # Remove unnessesary matching elements, spans or paragraphs
        if item.type == tag or item.type in ('span', 'p'):
          yield replace(
              item,
              type=tag,
              color=color,
          )
          return

    self.TAG_ITEMS_TYPES.setdefault(tag, set()).update((
        item.type
        for item in items
    ))

    if tag in ('h1', 'h2', 'choice', 'branch', 'imgfooter'):
      if not items:
        return

      anchor = (
          e.get('id')
          if constants.CLASS_ANCHOR in classes else
          None
      )

      if tag in ('branch', 'choice'):
        items = [tags.TagText(
            'text',
            (e.text or '').upper(),
        )]

      yield tags.TagTitle(
          tag,
          items,
          anchor,
      )
      return

    elif tag in ('a', 'button'):
      if not items:
        return

      url = util.rewrite_url(
          self.base_url,
          util.clean_url(e.get('href', '')),
          urls,
      )
      self.TAG_URLS.add(url)

      yield tags.TagLink(
          tag,
          items,
          url,
      )
      return

    elif tag in ('p', 'b', 'i', 'span', 'blockquote', 'ol', 'ul', 'li', 'code'):
      if not items:
        return

      highlight = util.get_color_for_class(
          classes,
          constants.CSS_HIGHLIGHT_COLORS,
      )
      if tag == 'p' and highlight:
        yield tags.TagHighlight(
            'highlight',
            items,
            highlight,
        )
        return
      else:
        yield tags.TagFormattedText(
            tag,
            items,
            color,
        )
        return

    elif tag == 'img':
      src = e.get('src', '')
      if src.startswith('/'):
        src = urljoin(self.base_url, src)

      yield tags.TagImg(
          tag,
          src,
      )
      return

    elif tag in ('hr', 'br'):
      yield tags.EmptyTag(tag)
      return
    elif tag not in ('title', 'mark'):
      print(tag)

  def parse_element_items(self, parent: HtmlElement, urls: dict[str, str], icon_color: str | None) -> Generator[tags.Tag]:
    if parent.text and parent.text:
      yield from self.process_text(parent.text, icon_color)

    for child in parent:
      yield from self.parse_element(child, urls, icon_color)

      if child.tail and child.tail:
        yield from self.process_text(child.tail, icon_color)

  def process_text(self, text: str, icon_color: str | None) -> Generator[tags.Tag]:
    start = 0
    i = 0
    for i, c in enumerate(text):
      code = ord(c)
      if 0xE000 <= code <= 0xF8FF:
        self.TAG_ICONS[c] = constants.RANGER_ICON_NAMES.get(c)

      if c in constants.RANGER_ICON_NAMES:
        if i > start:
          text = text[start:i].replace('\n', ' ')
          if text != '\u200b':
            yield tags.TagText(
                'text',
                text,
            )

        icon = tags.TagIcon(
            'icon',
            [tags.TagText(
                'text',
                '&nbsp;',
            )],
            constants.RANGER_ICON_NAMES[c],
        )
        yield tags.TagFormattedText(
            'span',
            [icon],
            icon_color,
        ) if icon_color else icon
        start = i + 1

    if i >= start:
      text = text[start:i+1].replace('\n', ' ')
      if text != '\u200b':
        yield tags.TagText(
            'text',
            text,
        )

  def get_lookup_group(self, resource_id: str):
    parts = resource_id.split('/')
    if parts[0] in ('campaign_guides', 'one_day_missions') and len(parts) > 1:
      return '/'.join(parts[:2])
    if parts[0] == 'rules_glossary':
      return parts[0]
    return None

  def content_to_xhtml(self, resource_id: str, content: Sequence[tags.Tag]):
    return ''.join((
        self.content_item_to_xhtml(resource_id, item)
        for item in content
    ))

  def content_item_to_xhtml(self, resource_id: str, content: tags.Tag):
    if isinstance(content, tags.TagText):
      return content.text

    attributes = {}

    if isinstance(content, tags.TagTitle):
      attributes['id'] = content.anchor

    elif isinstance(content, tags.TagHighlight):
      attributes['highlight'] = content.highlight

    elif isinstance(content, tags.TagIcon):
      icon = content.icon
      attributes['icon'] = icon
      if self.icon_type is IconType.TEXT:
        return f'[{icon}]'

    elif isinstance(content, tags.TagLink):
      href = content.href
      if href.startswith(f'{resource_id}#'):
        href = href.removeprefix(resource_id)
      attributes['href'] = href

    elif isinstance(content, tags.TagImg):
      attributes['src'] = content.src

    elif isinstance(content, tags.TagFormattedText):
      attributes['color'] = content.color

    if attributes:
      attributes = f'{' '.join(f'{k}="{html.escape(v, quote=True)}"' for k, v in attributes.items() if v)}'
    else:
      attributes = ''

    if attributes:
      attributes = f' {attributes}'

    if isinstance(content, tags.TagWithItems):
      items = self.content_to_xhtml(
          resource_id,
          content.items,
      )
      return f'<{content.type}{attributes}>{items}</{content.type}>'

    return f'<{content.type}{attributes} />'

  def scrape(self):
    rmtree(self.output_dir, ignore_errors=True)

    urls = dict[str, str]()
    titles = dict[str, str]()
    lookup = dict[str, list[dict[str, str]]]()
    for page_url in self.page_urls:
      for url, resource_id, title, _, _ in self.scrape_page(page_url):
        urls[url] = resource_id
        titles[url] = title

        lookup_group = self.get_lookup_group(resource_id)
        if lookup_group and lookup_group != resource_id:
          lookup.setdefault(lookup_group, []).append({
              'id': resource_id,
              'title': title,
          })

    for page_url in self.page_urls:
      for url, resource_id, title, items, data in self.scrape_page(page_url):
        file = self.output_dir / 'data' / f'{resource_id}.json'
        content = (
            list(self.parse_element_items(
                data,
                urls,
                None,
            ))
            if data is not None else
            None
        )
        if self.content_type == ContentType.XHTML:
          content = self.content_to_xhtml(
              resource_id,
              content,
          ) if content else None
        elif self.content_type == ContentType.JSON:
          content = [
              asdict(item)
              for item in content
          ] if content else None
        else:
          content = None

        lookup_group = self.get_lookup_group(resource_id)
        util.write_resource(
            file,
            resource_id,
            title,
            content,
            [
                {
                    'id': '/'.join((resource_id, item_id)),
                    'title': item_title,
                }
                for item_id, item_title, _ in items
            ],
            (
                lookup[lookup_group]
                if lookup_group and lookup_group == resource_id else
                []
            ),
            util.clean_url(url),
        )

      util.write_resource(
          self.output_dir / 'data.json',
          '',
          'The Living Valley',
          None,
          [
              {
                  'id': urls[page_url],
                  'title': titles[page_url],
              }
              for page_url in self.page_urls
          ],
          [],
          self.base_url,
      )

      self.dump_logs()

  def dump_logs(self):
    rmtree(self.log_dir, ignore_errors=True)

    util.write_json(
        (self.log_dir / 'tags.json'),
        {
            key: sorted(value)
            for key, value in sorted(self.TAG_ITEMS_TYPES.items(), key=lambda x: x[0])
        },
    )
    util.write_json(
        (self.log_dir / 'classes.json'),
        {
            key: sorted(value)
            for key, value in sorted(self.TAG_CLASSES.items(), key=lambda x: x[0])
        },
    )
    util.write_json(
        (self.log_dir / 'urls.json'),
        sorted(self.TAG_URLS),
    )
    util.write_json(
        (self.log_dir / 'icons.json'),
        dict(sorted(self.TAG_ICONS.items(), key=lambda x: x[0])),
    )
