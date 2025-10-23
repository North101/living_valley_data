from .main import Scraper, IconType, ContentType


if __name__ == "__main__":
  Scraper(
      'https://thelivingvalley.earthbornegames.com',
      [
          '/docs/category/campaign-guides',
          '/docs/rules_glossary',
          '/docs/one_day_missions',
          '/docs/category/updates',
          '/docs/faq',
      ],
      IconType.ELEMENT,
      ContentType.XHTML,
  ).scrape()
