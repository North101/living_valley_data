import enum
import html
import pathlib
from collections.abc import Generator, Sequence
from dataclasses import asdict, replace
from shutil import rmtree
from urllib.parse import urljoin

import requests
from lxml.html import HtmlElement
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from . import constants, tags, util


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
  RESOURCE_NARRATION_IDS = dict[str, int]()

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

  def narration_id(self, resource_id: str):
    narration_id = self.RESOURCE_NARRATION_IDS.setdefault(resource_id, 0) + 1
    self.RESOURCE_NARRATION_IDS[resource_id] = narration_id
    return f'narration_{narration_id}'

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

  def parse_element(self, resource_id: str, e: HtmlElement, urls: dict[str, str], icon_color: str | None) -> Generator[tags.Tag]:
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
        resource_id,
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
      if isinstance(item, (tags.TagFormattedText, tags.TagBlockquote)):
        # Remove trailing spaces
        if item.items and item.items[-1] == tags.TagText('text', ' '):
          item.items.pop()

    if tag in ('p', 'b', 'i', 'span'):
      if items and len(items) == 1 and (item := items[0]) and isinstance(item, (tags.TagFormattedText, tags.TagBlockquote)):
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

    elif tag == 'blockquote':
      yield tags.TagBlockquote(
          tag,
          items,
          self.narration_id(resource_id),
          color,
      )
      return

    elif tag in ('p', 'b', 'i', 'span', 'ol', 'ul', 'li', 'code'):
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

  def parse_element_items(self, resource_id: str, parent: HtmlElement, urls: dict[str, str], icon_color: str | None) -> Generator[tags.Tag]:
    if parent.text and parent.text:
      yield from self.process_text(parent.text, icon_color)

    for child in parent:
      yield from self.parse_element(resource_id, child, urls, icon_color)

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

  def find_anchors(self, items: Sequence[tags.Tag]) -> Generator[util.Link]:
    for item in items:
      yield from self.find_anchor(item)

  def find_anchor(self, item: tags.Tag) -> Generator[util.Link]:
    if isinstance(item, tags.TagTitle) and item.anchor:
      yield util.Link(
          id=f'#{item.anchor}',
          title=''.join((
              text
              for text in self.get_text(item)
          )),
      )
    if isinstance(item, tags.TagWithItems):
      yield from self.find_anchors(item.items)

  def find_narrations(self, resource_id: str, url: str, anchor: str | None, items: list[tags.Tag]) -> Generator[util.Narration]:
    for item in items:
      anchor = item.anchor if isinstance(item, tags.TagTitle) else anchor
      yield from self.find_narration(
          resource_id,
          url,
          anchor,
          item
      )

  def find_narration(self, resource_id: str, url: str, anchor: str | None, item: tags.Tag) -> Generator[util.Narration]:
    if isinstance(item, tags.TagBlockquote):
      yield util.Narration(
        resource_id,
        f'{url}#{anchor}' if anchor else url,
        item,
      )

    if isinstance(item, tags.TagWithItems):
      yield from self.find_narrations(
          resource_id,
          url,
          item.anchor if isinstance(item, tags.TagTitle) else anchor,
          item.items,
      )

  def get_text(self, item: tags.Tag) -> Generator[str]:
    if isinstance(item, tags.TagText):
      yield item.text
    elif isinstance(item, tags.TagWithItems):
      for subitem in item.items:
        yield from self.get_text(subitem)

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

    if isinstance(content, (tags.TagTitle, tags.TagBlockquote)):
      attributes['id'] = content.anchor

    if isinstance(content, tags.TagHighlight):
      attributes['highlight'] = content.highlight

    if isinstance(content, tags.TagIcon):
      icon = content.icon
      attributes['icon'] = icon
      if self.icon_type is IconType.TEXT:
        return f'[{icon}]'

    if isinstance(content, tags.TagLink):
      href = content.href
      if href.startswith(f'{resource_id}#'):
        href = href.removeprefix(resource_id)
      attributes['href'] = href

    if isinstance(content, tags.TagImg):
      attributes['src'] = content.src

    if isinstance(content, (tags.TagFormattedText, tags.TagBlockquote)):
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

  def content_to_text(self, items: list[tags.Tag]) -> Generator[str]:
    for item in items:
      yield from self.content_item_to_text(item)

  def content_item_to_text(self, item: tags.Tag) -> Generator[str]:
    if isinstance(item, tags.TagWithItems):
      if isinstance(item, tags.TagFormattedText) and item.type == 'p':
        yield '\n'.join(self.content_to_text(item.items))
      else:
        yield ''.join(self.content_to_text(item.items))

    if isinstance(item, tags.TagText):
      yield item.text

  def scrape(self):
    urls = dict[str, str]()
    titles = dict[str, str]()
    lookup = dict[str, list[util.Link]]()
    narrations = dict[str, list[util.Narration]]()
    for page_url in self.page_urls:
      for url, resource_id, title, _, _ in self.scrape_page(page_url):
        urls[url] = resource_id
        titles[url] = title

        lookup_group = self.get_lookup_group(resource_id)
        if lookup_group and lookup_group != resource_id:
          lookup.setdefault(lookup_group, []).append(util.Link(
              id=resource_id,
              title=title,
          ))

    rmtree(self.output_dir, ignore_errors=True)
    for page_url in self.page_urls:
      for url, resource_id, title, items, data in self.scrape_page(page_url):
        file = self.output_dir / 'data' / f'{resource_id}.json'
        content = (
            list(self.parse_element_items(
                resource_id,
                data,
                urls,
                None,
            ))
            if data is not None else
            None
        )
        anchors = (
            list(self.find_anchors(content))
            if content else
            []
        )

        lookup_group = self.get_lookup_group(resource_id)
        if lookup_group:
          narrations.setdefault(lookup_group, []).extend(
              list(self.find_narrations(resource_id, url, None, content))
              if content else
              []
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
            anchors,
            [
                util.Link(
                    id='/'.join((resource_id, item_id)),
                    title=item_title,
                )
                for item_id, item_title, _ in items
            ] + anchors,
            (
                lookup[lookup_group]
                if lookup_group and lookup_group == resource_id else
                []
            ),
            util.clean_url(url),
        )

    for story_id, narrations in narrations.items():
      util.write_csv(
          self.output_dir / 'csv' / f'{story_id}.csv',
          [
              util.NarrationItem(
                  '.'.join(f'{narration.resource_id}/{narration.tag.anchor}'.split('/')),
                  urljoin(self.base_url, narration.url),
                  '\n'.join(self.content_to_text(
                      narration.tag.items,
                  )),
              )
              for narration in narrations
          ],
      )

    util.write_resource(
        self.output_dir / 'data.json',
        '',
        'The Living Valley',
        None,
        [],
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
