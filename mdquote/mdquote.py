#!/usr/bin/env python3
"""Print a Markdown quote of a social media post.

Supported sites: X (Twitter) and Bluesky.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

USER_AGENT = "mdquote/0.1 (+https://github.com/miikka/scratch)"

X_HOSTS = {
    "x.com",
    "twitter.com",
    "mobile.twitter.com",
    "mobile.x.com",
    "fxtwitter.com",
    "vxtwitter.com",
    "fixupx.com",
    "fixvx.com",
}
X_STATUS_RE = re.compile(r"^/(?:[^/]+|i/web)/status(?:es)?/(\d+)")

BSKY_HOSTS = {"bsky.app", "staging.bsky.app"}
BSKY_POST_RE = re.compile(r"^/profile/([^/]+)/post/([^/]+)")
BSKY_API = "https://public.api.bsky.app/xrpc"


@dataclass
class Post:
    author: str
    site: str
    url: str
    text: str


def fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def fetch_x(status_id: str) -> Post:
    # The FxTwitter API serves public tweets without authentication.
    data = fetch_json(f"https://api.fxtwitter.com/status/{status_id}")
    tweet = data.get("tweet")
    if not tweet:
        raise RuntimeError(f"could not fetch tweet: {data.get('message', data)}")
    author = tweet["author"]
    return Post(
        author=author.get("name") or author["screen_name"],
        site="X",
        url=tweet["url"],
        text=tweet["text"],
    )


def resolve_bsky_handle(actor: str) -> str:
    if actor.startswith("did:"):
        return actor
    query = urllib.parse.urlencode({"handle": actor})
    return fetch_json(f"{BSKY_API}/com.atproto.identity.resolveHandle?{query}")["did"]


def bsky_text_with_links(record: dict[str, Any]) -> str:
    """Replace link facets (which are often truncated in the text) with Markdown links."""
    text: str = record.get("text", "")
    raw = text.encode("utf-8")
    links = []
    for facet in record.get("facets", []):
        for feature in facet.get("features", []):
            if feature.get("$type") == "app.bsky.richtext.facet#link":
                index = facet["index"]
                links.append((index["byteStart"], index["byteEnd"], feature["uri"]))
    out = []
    pos = 0
    for start, end, uri in sorted(links):
        if start < pos:
            continue
        label = raw[start:end].decode("utf-8", errors="replace")
        out.append(raw[pos:start].decode("utf-8", errors="replace"))
        out.append(uri if label == uri else f"[{label}]({uri})")
        pos = end
    out.append(raw[pos:].decode("utf-8", errors="replace"))
    return "".join(out)


def fetch_bsky(actor: str, rkey: str) -> Post:
    did = resolve_bsky_handle(actor)
    uri = f"at://{did}/app.bsky.feed.post/{rkey}"
    query = urllib.parse.urlencode({"uris": uri})
    posts = fetch_json(f"{BSKY_API}/app.bsky.feed.getPosts?{query}")["posts"]
    if not posts:
        raise RuntimeError(f"post not found: {uri}")
    post = posts[0]
    author = post["author"]
    handle = author["handle"]
    return Post(
        author=author.get("displayName") or handle,
        site="Bluesky",
        url=f"https://bsky.app/profile/{handle}/post/{rkey}",
        text=bsky_text_with_links(post["record"]),
    )


def fetch_post(url: str) -> Post:
    parsed = urllib.parse.urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or "").removeprefix("www.")
    if host in X_HOSTS and (m := X_STATUS_RE.match(parsed.path)):
        return fetch_x(m.group(1))
    if host in BSKY_HOSTS and (m := BSKY_POST_RE.match(parsed.path)):
        return fetch_bsky(m.group(1), m.group(2))
    raise ValueError(f"unsupported URL: {url}")


def format_quote(post: Post) -> str:
    lines = [f"[{post.author} on {post.site}]({post.url}):"]
    for line in post.text.strip().splitlines():
        lines.append(f"> {line}".rstrip())
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("url", help="Link to an X or Bluesky post.")
    args = parser.parse_args()
    try:
        post = fetch_post(args.url)
    except (ValueError, RuntimeError, OSError) as e:
        print(f"mdquote: {e}", file=sys.stderr)
        return 1
    print(format_quote(post))
    return 0


if __name__ == "__main__":
    sys.exit(main())
