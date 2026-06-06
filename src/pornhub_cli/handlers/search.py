"""Search handlers for the Pornhub CLI."""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag

from pornhub_cli.handlers.requests import session


def filter_ad(video: Tag) -> bool:
    """Filter out ad items from the list of video items."""
    if video.get_text(strip=True) == "Remove Ads":
        return True
    return False


def search(query: str, page: int=1) -> tuple[list[str], list[dict[str, str]]]:
    """Search for videos matching the query."""
    url = f"https://www.pornhub.com/video/search?search={query}&page={page}"
    resp = session.get(url)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    videos = soup.find(id="videoSearchResult").find_all("li")

    recommendations = soup.find_all("a", class_="gtm-event-related-searches")
    recommendations = [recommendation.get_text(strip=True) for recommendation in recommendations]

    video_list = []
    for video in videos:
        if filter_ad(video):
            continue
        duration = video.find(class_="duration").get_text(strip=True)
        views = video.find(class_="views").get_text(strip=True)
        added = video.find(class_="added").get_text(strip=True)
        title = video.find("img").get("title").strip()
        author = video.find(class_="usernameWrap").a.get_text(strip=True)
        view_key = video.get("data-video-vkey").strip()
        video_list.append({"duration": duration, "views": views, "added": added, "title": title, "author": author, "view_key": view_key})

    return recommendations, video_list
