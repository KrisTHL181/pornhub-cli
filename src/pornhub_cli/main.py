"""pornhub CLI — unified entry point for all PornHub operations."""

import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from queue import Queue

import click

from pornhub_cli.utils import convert_time_unit

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
    click.echo(f"Recommendations: {', '.join(recommendations)}")
    click.echo(f"Found {len(video_list)} videos:")
    for video in video_list:
        click.echo(
            f" - {video['title']} by {video['author']} — {video['duration']}, {video['views']} views, added {video['added']} (view key: {video['view_key']})"
        )


@main.group()
def video() -> None:
    """Video-related operations."""


@video.command()
@click.argument("view_key", type=str)
def get_video_info(view_key: str) -> None:
    """Get video information and media URLs for a given view key."""
    from pornhub_cli.handlers.video import get_video_data, list_qualities, get_video_urls_for_quality
    from pornhub_cli.handlers.requests import download

    video_data = get_video_data(view_key)
    click.echo(f"Title: {video_data['title']}")
    click.echo(f"Duration: {convert_time_unit(video_data['duration'])}")
    click.echo("Available qualities:")
    qualities = list_qualities(video_data)
    quality_labels = [q["quality"] for q in qualities]
    for label in quality_labels:
        click.echo(f" - {label}p")
    quality_choice = click.prompt(
        "Which quality do you want to download?",
        type=click.Choice(quality_labels),
        show_choices=True,
    )

    # Parse the m3u8 playlist only for the user-selected quality
    click.echo(f"Fetching {quality_choice}p video segments...")
    urls = get_video_urls_for_quality(qualities, quality_choice)
    if not urls:
        click.echo(f"No segments found for quality '{quality_choice}'.", err=True)
        sys.exit(1)

    quality = quality_choice
    click.echo(f"Downloading {quality}p video...")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Position pool — each worker thread occupies one tqdm row
        max_workers = 8
        position_pool = Queue(maxsize=max_workers)
        for i in range(max_workers):
            position_pool.put(i)

        def download_segment(idx, url_info, view_key, quality, temp_path):
            url = url_info["url"]
            duration = url_info["duration"]
            pos = position_pool.get()
            try:
                data = download(url, desc=f"Seg {idx:>3}", position=pos)
                filename = temp_path / f"{view_key}_{quality}_{duration}_{idx}.ts"
                filename.write_bytes(data)
                return idx, True, None
            except Exception as e:
                return idx, False, str(e)
            finally:
                position_pool.put(pos)

        failed_segments = []

        # Parallel download — per-segment tqdm bars show progress and speed
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(download_segment, idx, url_info, view_key, quality, temp_path): idx
                for idx, url_info in enumerate(urls, 1)
            }

            for future in as_completed(futures):
                idx, success, error = future.result()
                if not success:
                    failed_segments.append((idx, error))

        # Retry failed segments with freshly-fetched URLs
        if failed_segments:
            click.echo("Re-fetching segment URLs for retry...")
            fresh_urls = get_video_urls_for_quality(qualities, quality)

            for idx, error in failed_segments:
                if idx - 1 < len(fresh_urls):
                    url_info = fresh_urls[idx - 1]
                else:
                    click.echo(f"Segment {idx} — fresh URL list has no index {idx}. Skipping.")
                    continue

                _, success, error = download_segment(idx, url_info, view_key, quality, temp_path)
                if not success:
                    click.echo(f"Segment {idx} failed again with error: {error}. Skipping.")

        click.echo("✓ Download complete.")

        concat_list_content = ""
        for idx in range(1, len(urls) + 1):
            url_info = urls[idx - 1]
            duration = url_info["duration"]
            filename = f"{view_key}_{quality}_{duration}_{idx}.ts"
            concat_list_content += f"file '{temp_path / filename}'\n"

        list_file_path = temp_path / "filelist.txt"
        list_file_path.write_text(concat_list_content, encoding="utf-8")

        output_mp4 = f"{view_key}_{quality}.mp4"
        click.echo("Merging segments via ffmpeg-python...")

        import ffmpeg

        try:
            (
                ffmpeg.input(str(list_file_path), f="concat", safe=0)
                .output(str(output_mp4), c="copy")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            click.echo(f"✓ Video merged successfully: {output_mp4}")
        except ffmpeg.Error as e:
            click.echo(f"❌ FFmpeg merge failed: {e.stderr.decode('utf-8')}")
