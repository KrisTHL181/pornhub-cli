"""pornhub CLI — unified entry point for all PornHub operations."""

import click


# ── CLI root ─────────────────────────────────────────────────────────────


@click.group()
@click.version_option(version="0.1.0", prog_name="pornhub")
def main() -> None:
    """pornhub — PornHub scraping, automation, and analysis toolkit."""


# ── auth ─────────────────────────────────────────────────────────────────


@main.group()
def search() -> None:
    """Search for videos matching a query."""

@search.command()
@click.argument("query", type=str)
@click.option("--page", "-p", default=1, help="Page number to fetch.")
def search_videos(query: str, page: int) -> None:
    """Search for videos matching the query."""
    from pornhub_cli.handlers.search import search

    recommendations, video_list = search(query, page)
    click.echo(f"Recommendations: {recommendations}")
    click.echo(f"Videos: {video_list}")
