# living_valley_data

Run script
```
uv run -m app
```

The first time it runs it will fetch each page from https://thelivingvalley.earthbornegames.com/ and cache it to `./cache/`.
Afterwards it'll be almost instant as it'll read the files from `./cache/` instead of downloading them.

```json
{
  "id": string,
  "title": string,
  "content": string | null,
  "links": [{
    "id": string,
    "title": string
  }],
  "lookup": {
    "title": string,
    "links": [{
      "id": string,
      "title": string
    }]
  },
  "url": string
}
```

## id
The id of the resource. It's also the path to that resource

## title

The title of the resource

## links

Links to any direct descendants of this resource

## content

Page content. This is represented as html along with some custom tags

### Content Tags
| Tag            | Description     | Attributes                                                                    |
| -------------- | --------------- | ----------------------------------------------------------------------------- |
| `<h1>`         | Big Header      | —                                                                             |
| `<h2>`         | Small Header    | —                                                                             |
| `<choice>`     | Choice Header   | —                                                                             |
| `<branch>`     | Branch Header   | —                                                                             |
| `<highligh>`   | Highlight block | `highlight="blue"`<br>`highlight="clear"`                                     |
| `<blockquote>` | Story Text      | —                                                                             |
| `<code>`       | Errata          | —                                                                             |
| `<ol>`         | Ordered List    | —                                                                             |
| `<ul>`         | Unordered List  | —                                                                             |
| `<li>`         | List Item       | —                                                                             |
| `<a>`          | Link            | `href`                                                                        |
| `<p>`          | Paragraph       | `color="red"`<br>`color="blue"`<br>`color="gold"`<br>`color="green"`              |
| `<span>`       | Text            | `color="red"`<br>`color="blue"`<br>`color="gold"`<br>`color="green"`              |
| `<b>`          | Bold            | —                                                                             |
| `<i>`          | Italics         | —                                                                             |
| `<icon>`       | Icon            | `icon="<icon>"`<br>`color="red"`<br>`color="blue"`<br>`color="gold"`<br>`color="green"` |

## lookup

## url
The original url for the resource
