from abc import ABC
from dataclasses import dataclass
from typing import Any, Literal


EmptyType = Literal['hr', 'br']
TextType = Literal['text']
TitleType = Literal['h1', 'h2', 'choice', 'branch', 'imgfooter']
FormattedTextType = Literal['p', 'b', 'i', 'span', 'ol', 'ul', 'li', 'code']
BlockquoteType = Literal['blockquote']
IconType = Literal['icon']
HighlightType = Literal['highlight']
LinkType = Literal['a', 'button']
ImgType = Literal['img']
MissionType = Literal['mission']
EventType = Literal['event']
RewardType = Literal['reward']
EntryType = Literal['entry']


@dataclass
class Tag[T: str]:
  type: T


class TagWithItems[T: str](Tag[T], ABC):
  items: list[Tag[Any]]


@dataclass
class EmptyTag(Tag[EmptyType]):
  pass


@dataclass
class TagText(Tag[TextType]):
  text: str


@dataclass
class TagTitle(TagWithItems[TitleType]):
  id: str | None
  items: list[Tag[Any]]


@dataclass
class TagFormattedText(TagWithItems[FormattedTextType]):
  color: str | None
  items: list[Tag[Any]]


@dataclass
class TagBlockquote(TagWithItems[BlockquoteType]):
  id: str
  color: str | None
  items: list[Tag[Any]]


@dataclass
class TagIcon(TagWithItems[IconType]):
  icon: str
  items: list[Tag[Any]]


@dataclass
class TagHighlight(TagWithItems[HighlightType]):
  highlight: str
  items: list[Tag[Any]]


@dataclass
class TagLink(TagWithItems[LinkType]):
  href: str
  items: list[Tag[Any]]


@dataclass
class TagImg(Tag[ImgType]):
  src: str


@dataclass
class TagMission(TagWithItems[MissionType]):
  items: list[Tag[TextType]]


@dataclass
class TagEvent(TagWithItems[EventType]):
  items: list[Tag[TextType]]


@dataclass
class TagEntry(TagWithItems[EntryType]):
  items: list[Tag[TextType]]


@dataclass
class TagReward(TagWithItems[RewardType]):
  items: list[Tag[TextType]]
