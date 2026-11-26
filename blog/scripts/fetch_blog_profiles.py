"""Read exact CMS speaker names from public article relations; no CMS mutation."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import urllib.parse

from article_materials import ROOT, job_path, write_json
from strapi_publish import API, api, read_author


def profile_records(response, expected):
    rows = response.get('data', response) if isinstance(response, dict) else response
    found = {}
    for article in rows:
        article = article.get('attributes', article)
        for relation in ('author', 'editors'):
            people = article.get(relation, [])
            if isinstance(people, dict) and 'data' in people:
                people = people['data']
            for person in people if isinstance(people, list) else [people]:
                if not isinstance(person, dict):
                    continue
                fields = person.get('attributes', person)
                ident = person.get('id')
                if ident not in expected.values():
                    continue
                name = fields.get('name')
                if not isinstance(name, str) or not name.strip():
                    continue
                username = next(k for k, value in expected.items() if value == ident)
                if fields.get('username') and fields['username'] != username:
                    raise ValueError('CMS profile ID/username mismatch')
                record = {'id': ident, 'username': username, 'name': name}
                if username in found and found[username] != record:
                    raise ValueError('CMS returned conflicting speaker names')
                found[username] = record
    if set(found) != set(expected):
        raise ValueError('Missing CMS speaker names: ' + ', '.join(sorted(set(expected) - set(found))))
    return [found[key] for key in expected]


def fetch(job):
    author = read_author(job)
    mapping = json.loads((ROOT / 'config/blog-authors.json').read_text())
    expected = {key: mapping[key] for key in dict.fromkeys([author, mapping['defaults']['editor']])}
    query = urllib.parse.urlencode({'filters[author][id][$eq]': expected[author],
        'sort': 'id:desc', 'pagination[pageSize]': 5,
        'populate[author]': '*', 'populate[editors]': '*'})
    source = API + '/articles?' + query
    records = profile_records(api('/articles?' + query), expected)
    path = job / 'raw/speaker-profiles.json'
    path.parent.mkdir(exist_ok=True)
    write_json(path, {'source': source, 'checked_at': datetime.now(timezone.utc).isoformat(),
                     'profiles': records})
    print(path)
    for record in records:
        print(record['username'] + ': ' + record['name'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', required=True)
    args = parser.parse_args()
    fetch(job_path(args.job))
