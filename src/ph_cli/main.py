"""pornhub CLI — unified entry point for all PornHub operations."""

import click


# ── CLI root ─────────────────────────────────────────────────────────────


@click.group()
@click.version_option(version="0.1.0", prog_name="pornhub")
def main() -> None:
    """pornhub — PornHub scraping, automation, and analysis toolkit."""


# ── auth ─────────────────────────────────────────────────────────────────


@main.group()
def auth() -> None:
    """Manage authentication."""


@auth.command("status")
def auth_status() -> None:
    """Show authentication status."""
    click.echo("Not yet implemented.")
