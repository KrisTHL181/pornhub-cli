"""Video handlers for the Pornhub CLI."""

from __future__ import annotations

import json
import re

import m3u8

from pornhub_cli.handlers.requests import M3U8HttpClient, session

# Use our impersonated, header-rich session for m3u8 playlist fetches
# instead of the default urllib client (which sends no Referer / Origin
# and can trigger CDN throttling even for tiny playlist files).
_m3u8_http = M3U8HttpClient(session)


def get_video_data(view_key: str) -> dict[str, str]:
    resp = session.get(f"https://www.pornhub.com/view_video.php?viewkey={view_key}")
    html_content = resp.text
    match = re.search(r"var flashvars_\d+\s*=\s*(\{.*?\});", html_content, re.DOTALL)
    if not match:
        raise ValueError("Could not find flashvars in the video page.")

    flashvars_json = match.group(1)
    flashvars = json.loads(flashvars_json)

    video_title = flashvars.get("video_title", "unknown")
    video_duration = flashvars.get("video_duration", "unknown")
    media_definitions = flashvars.get("mediaDefinitions", [])
    video_info = {"title": video_title, "duration": video_duration, "media_definitions": media_definitions}
    return video_info


def parse_m3u8_playlist(m3u8_url: str) -> list[dict[str, str]]:
    master = m3u8.load(m3u8_url, http_client=_m3u8_http)
    base_url = m3u8_url.split("master.m3u8")[0]

    playlist = m3u8.load(base_url + master.playlists[0].uri, http_client=_m3u8_http)

    video_urls = []
    for segment in playlist.segments:
        video_urls.append({"url": base_url + segment.uri, "duration": segment.duration})
    return video_urls

def list_qualities(video_data: dict[str, str]) -> list[dict[str, str]]:
    """Return available quality labels and their m3u8 URLs without parsing the playlists."""
    media_definitions = video_data.get("media_definitions", [])
    # the last one is a loopback to the master playlist, which we don't need
    if media_definitions:
        media_definitions = media_definitions[:-1]

    qualities = []
    for media in media_definitions:
        m3u8_url = media.get("videoUrl")
        if m3u8_url:
            qualities.append({"quality": media.get("quality"), "m3u8_url": m3u8_url})
    return qualities


def get_video_urls_for_quality(qualities: list[dict[str, str]], target_quality: str) -> list[dict[str, str]]:
    """Parse the m3u8 playlist for a specific quality and return segment URLs."""
    for entry in qualities:
        if entry["quality"] == target_quality:
            return parse_m3u8_playlist(entry["m3u8_url"])
    return []
