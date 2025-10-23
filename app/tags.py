from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class Tag():
  type: Any


@dataclass
class TagWithItems(Tag):
  items: list[Tag]


@dataclass
class EmptyTag(Tag):
  type: Literal['hr', 'br']


@dataclass
class TagText(Tag):
  type: Literal['text']
  text: str


@dataclass
class TagTitle(TagWithItems):
  type: Literal['h1', 'h2', 'choice', 'branch', 'imgfooter']
  anchor: str | None


@dataclass
class TagFormattedText(TagWithItems):
  type: Literal['p', 'b', 'i', 'span', 'blockquote', 'ol', 'ul', 'li', 'code']
  color: str | None


@dataclass
class TagIcon(TagWithItems):
  type: Literal['icon']
  icon: str


@dataclass
class TagHighlight(TagWithItems):
  type: Literal['highlight']
  highlight: str


@dataclass
class TagLink(TagWithItems):
  type: Literal['a', 'button']
  href: str


@dataclass
class TagImg(Tag):
  type: Literal['img']
  src: str
