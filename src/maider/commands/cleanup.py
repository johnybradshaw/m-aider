"""Remove stale VM sessions."""

import shutil

import click
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..config import Config
from ..linode_client import LinodeManager
from ..output import console
from ..session import SessionManager


@click.command(name="cleanup")
@click.option(
    "--session", "-s", help="Clean up a specific session (force-remove if --force is set)"
)
@click.option("--force", "-f", is_flag=True, help="Force removal without checking if VM exists")
def cmd(session: str, force: bool):
    """Remove stale VM sessions.

    Removes session directories where:
    - The Linode VM no longer exists
    - The session state file is missing or corrupted

    Use --session to target a specific session (e.g., after manually deleting the VM).
    Use --force to skip VM existence check (for manual cleanup).
    """
    session_mgr = SessionManager()

    if session:
        _cleanup_single_session(session_mgr, session, force)
        return

    _cleanup_bulk_sessions(session_mgr)


def _cleanup_single_session(session_mgr: SessionManager, session: str, force: bool):
    target_session = session_mgr.get_session(session)
    if not target_session:
        console.print(f"[red]Session '{session}' not found[/red]")
        return

    console.print(f"[bold]Cleaning up session: {session}[/bold]\n")
    console.print(f"  Linode ID: {target_session.linode_id}")
    console.print(f"  IP: {target_session.ip}")

    if force:
        _force_remove_session(session_mgr, session, target_session)
        return

    _remove_session_if_vm_missing(session_mgr, session, target_session)


def _force_remove_session(session_mgr: SessionManager, session: str, target_session):
    console.print("\n[yellow]⚠ Force mode enabled - skipping VM existence check[/yellow]")
    response = input("\nRemove local session state? [y/N]: ")
    if response.lower() != "y":
        console.print("Cancelled")
        return

    session_dir = session_mgr.cache_dir / session
    shutil.rmtree(session_dir)
    console.print(f"[green]✓ Removed local session state: {session}[/green]")
    console.print("\n[yellow]Note: If the VM still exists, you must delete it manually:[/yellow]")
    console.print(f"  https://cloud.linode.com/linodes/{target_session.linode_id}")


def _remove_session_if_vm_missing(session_mgr: SessionManager, session: str, target_session):
    try:
        config = Config()
        linode_mgr = LinodeManager(config)
        instance = linode_mgr.get_instance(target_session.linode_id)
    except Exception as e:
        console.print(f"[red]✗ Cannot check VM status: {e}[/red]")
        console.print("\nUse --force to skip VM check and remove local state anyway")
        return

    if instance:
        console.print(f"\n[yellow]⚠ VM {target_session.linode_id} still exists![/yellow]")
        console.print("\n[bold]Options:[/bold]")
        console.print(f"  1. Delete the VM first: coder down {session}")
        console.print(
            "  2. Force-remove local state anyway: coder cleanup --session {} --force".format(
                session
            )
        )
        console.print("  3. Manually delete from web dashboard:")
        console.print(f"     https://cloud.linode.com/linodes/{target_session.linode_id}")
        return

    session_dir = session_mgr.cache_dir / session
    shutil.rmtree(session_dir)
    console.print(f"[green]✓ Removed orphaned session: {session}[/green]")
    console.print(f"[dim](Linode {target_session.linode_id} no longer exists)[/dim]")


def _cleanup_bulk_sessions(session_mgr: SessionManager):
    sessions = session_mgr.list_sessions()

    if not sessions:
        console.print("[yellow]No sessions to clean up[/yellow]")
        return

    console.print("[bold]Checking for stale sessions...[/bold]\n")
    linode_mgr = _get_linode_manager()

    removed_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Checking sessions...", total=len(sessions))

        for session in sessions:
            removed = _cleanup_session_dir(session_mgr, linode_mgr, session)
            if removed:
                removed_count += 1
            progress.advance(task)

    console.print()
    if removed_count > 0:
        console.print(f"[green]✓ Removed {removed_count} stale session(s)[/green]")
    else:
        console.print("[green]✓ No stale sessions found[/green]")


def _get_linode_manager():
    try:
        config = Config()
        return LinodeManager(config)
    except Exception:
        console.print(
            "[yellow]⚠ No LINODE_TOKEN - can only remove sessions "
            "with missing state files[/yellow]\n"
        )
        return None


def _cleanup_session_dir(session_mgr: SessionManager, linode_mgr, session):
    session_dir = session_mgr.cache_dir / session.name
    state_file = session_dir / "state.json"
    if not state_file.exists():
        console.print(f"[yellow]  Removing session with missing state: {session.name}[/yellow]")
        shutil.rmtree(session_dir)
        return True

    if not linode_mgr:
        return False

    try:
        instance = linode_mgr.get_instance(session.linode_id)
        if not instance:
            console.print(
                f"[yellow]  Removing stale session: {session.name} "
                f"(Linode {session.linode_id} no longer exists)[/yellow]"
            )
            shutil.rmtree(session_dir)
            return True
    except Exception:
        pass

    return False
