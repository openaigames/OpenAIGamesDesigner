"""Check local Markdown destinations and repository heading anchors."""
from collections import Counter
from pathlib import Path
import re
import unicodedata
from urllib.parse import unquote


def prose_lines(content):
    fence = None
    for number, line in enumerate(content.splitlines(), 1):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if marker:
            chars = marker.group(1)
            if fence is None:
                fence = chars
            elif chars[0] == fence[0] and len(chars) >= len(fence):
                fence = None
            continue
        if fence is None:
            yield number, line


def heading_anchors(content):
    anchors, counts = set(), Counter()
    for _, line in prose_lines(content):
        anchors.update(re.findall(r'\b(?:id|name)=[\"\']([^\"\']+)', line))
        match = re.match(r'^ {0,3}#{1,6}\s+(.+?)(?:\s+#+)?$', line)
        if not match:
            continue
        label = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', match.group(1))
        label = re.sub(r'<[^>]*>', '', label).replace('`', '').replace('*', '').lower().strip()
        # GitHub-style anchors for the ATX headings used by this repository.
        key = ''.join(c for c in label if c in '-_ ' or unicodedata.category(c)[0] in 'LNM').replace(' ', '-')
        suffix = '-' + str(counts[key]) if counts[key] else ''
        anchors.add(key + suffix)
        counts[key] += 1
    return anchors


def local_reference_errors(files):
    errors, cache = [], {}
    for path in files:
        path = Path(path)
        for number, line in prose_lines(path.read_text(encoding='utf-8-sig')):
            for target in re.findall(r'\[[^\]\n]*\]\(([^)\n]+)\)', line):
                target = target.strip().split(' "')[0].strip('<>')
                if re.match(r'^[a-zA-Z][\w+.-]*:', target) or '{{' in target:
                    continue
                file, _, fragment = target.partition('#')
                destination = (path.parent / unquote(file)).resolve() if file else path.resolve()
                if not destination.exists():
                    errors.append((str(path), number, target, 'missing file'))
                elif fragment and destination.is_file() and destination.suffix.lower() == '.md':
                    if destination not in cache:
                        cache[destination] = heading_anchors(destination.read_text(encoding='utf-8-sig'))
                    if unquote(fragment) not in cache[destination]:
                        errors.append((str(path), number, target, 'missing heading'))
    return errors
