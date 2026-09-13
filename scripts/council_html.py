"""Explicit block directions survive Outlook's removal of inherited RTL styles."""
from html import escape
from html.parser import HTMLParser

BLOCKS = {'html', 'body', 'div', 'section', 'h1', 'h2', 'h3', 'h4', 'p', 'ul', 'ol',
          'li', 'table', 'thead', 'tbody', 'tr', 'th', 'td'}


class _Directions(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag in BLOCKS or attrs.get('dir') in ('rtl', 'ltr'):
            direction = attrs.setdefault('dir', 'rtl')
            align = 'left' if direction == 'ltr' else 'right'
            style = attrs.get('style', '').rstrip(';')
            attrs['style'] = f'{style};direction:{direction};text-align:{align};'.lstrip(';')
        encoded = ''.join(f' {key}="{escape(value, quote=True)}"' if value is not None else f' {key}' for key, value in attrs.items())
        self.parts.append(f'<{tag}{encoded}>')

    def handle_endtag(self, tag): self.parts.append(f'</{tag}>')
    def handle_data(self, data): self.parts.append(data)
    def handle_entityref(self, name): self.parts.append(f'&{name};')
    def handle_charref(self, name): self.parts.append(f'&#{name};')
    def handle_decl(self, decl): self.parts.append(f'<!{decl}>')
    def handle_comment(self, text): self.parts.append(f'<!--{text}-->')


def normalize_directions(document):
    parser = _Directions()
    parser.feed(document)
    parser.close()
    return ''.join(parser.parts)
