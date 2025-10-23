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
  "lookup":  [{
    "id": string,
    "title": string
  }],
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
| `<h1>`         | Header 1        | —                                                                             |
| `<h2>`         | Header 2        | —                                                                             |
| `<choice>`     | Choice Header   | —                                                                             |
| `<branch>`     | Branch Header   | —                                                                             |
| `<highlight>`  | Highlight block | `highlight="blue"`<br>`highlight="clear"`                                     |
| `<blockquote>` | Story Text      | —                                                                             |
| `<code>`       | Errata          | —                                                                             |
| `<ol>`         | Ordered List    | —                                                                             |
| `<ul>`         | Unordered List  | —                                                                             |
| `<li>`         | List Item       | —                                                                             |
| `<a>`          | Link            | `href`                                                                        |
| `<p>`          | Paragraph       | `color="red"`<br>`color="blue"`<br>`color="gold"`<br>`color="green"`          |
| `<span>`       | Text            | `color="red"`<br>`color="blue"`<br>`color="gold"`<br>`color="green"`          |
| `<b>`          | Bold            | `color="red"`<br>`color="blue"`<br>`color="gold"`<br>`color="green"`          |
| `<i>`          | Italics         | `color="red"`<br>`color="blue"`<br>`color="gold"`<br>`color="green"`          |
| `<icon>`       | Icon            | `icon="<icon>"`                                                               |

## lookup

## url
The original url for the resource
