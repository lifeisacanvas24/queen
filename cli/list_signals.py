#!/usr/bin/env python3
from queen.technicals.signals.registry import names_with_modules
from rich.console import Console
from rich.table import Table

console = Console()


def main():
    console.rule("📦 Queen Signal Registry Overview")
    rows = names_with_modules()
    if not rows:
        console.print("[yellow]No signals discovered (check packages/env).[/yellow]")
        return

    tbl = Table(show_header=True, header_style="bold cyan")
    tbl.add_column("Signal (canonical)", style="white")
    tbl.add_column("Source module", style="dim")

    for name, mod in rows:
        tbl.add_row(name, mod)

    console.print(tbl)
    console.print(f"[dim]Total: {len(rows)}[/dim]")


if __name__ == "__main__":
    main()
