USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36'

SECTION_MARKDOWN = '//div[@class="theme-doc-markdown markdown"]'
NAV_PARENT_URLS = '//div[@class="sidebar_njMd"]/nav[@class="menu thin-scrollbar menu_SIkG"]//a[contains(@class, "menu__link--active")]'
NEXT_NAV_PARENT = '(./parent::div/parent::ul/parent::li/div/a[1] | ./parent::ul/parent::li/div/a[1])'
NAV_ITEM_URLS = '//div[@class="sidebar_njMd"]/nav[@class="menu thin-scrollbar menu_SIkG"]//div[@class="menu__list-item-collapsible menu__list-item-collapsible--active"]/parent::li/ul//a'
PAGE_TITLE = '(//header/h1//text() | //article/div/h1//text())'

CSS_TEXT_COLORS: dict[str, str] = {
    'blue_text': 'blue',
    'red_text': 'red',
    'gold_text': 'gold',
    'green_text': 'green',
}
CSS_ICON_COLORS: dict[str, str] = {
    'ranger_icons_red': 'red',
}
CSS_HIGHLIGHT_COLORS: dict[str, str] = {
    'blue_highlight': 'blue',
    'clear_highlight': 'clear',
}
CLASS_ANCHOR = 'anchor'


REPLACE_TAG: dict[str, str] = {
  'h1': 'title',
  'h2': 'h1',
  'h3': 'h2',
  'h4': 'choice',
  'h5': 'branch',
  'h6': 'imgfooter',
  'strong': 'b',
  'em': 'i',
  'div': 'p',
}


RANGER_ICON_NAMES: dict[str, str] = {
    "\ue010": "reason",
    "\ue011": "conflict",
    "\ue012": "connection",
    "\ue013": "exploration",
    "\ue014": "presence",
    "\ue015": "harm",
    "\ue016": "progress",
    "\ue017": "crest",
    "\ue018": "mountain",
    "\ue019": "sun",
    "\ue01a": "reshuffle",
    "\ue01b": "conditional",
    "\ue01c": "guide_entry",
    "\ue01d": "per_ranger",
    "\ue01e": "ranger_token",
    "\ue020": "write",  # ?
    "\ue021": "flooded_passage",
    "\ue022": "locked_passage",
    "\ue023": "overgrown_passage",
    "\ue024": "two_cards",  # ?
    "\ue025": "per_g",  # ?
}
