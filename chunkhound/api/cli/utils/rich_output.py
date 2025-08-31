"""Modern Rich-based output formatting utilities for ChunkHound CLI commands."""

from typing import Any, Dict, Optional, Union
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.progress import (
    Progress, 
    TaskID,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
    MofNCompleteColumn,
    SpinnerColumn,
    TimeElapsedColumn
)
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.align import Align


class RichOutputFormatter:
    """Modern terminal UI formatter using Rich library."""

    def __init__(self, verbose: bool = False):
        """Initialize Rich output formatter.

        Args:
            verbose: Whether to enable verbose output
        """
        self.verbose = verbose
        self.console = Console()
        self._progress: Optional[Progress] = None
        self._live: Optional[Live] = None
        
    def info(self, message: str) -> None:
        """Print an info message."""
        self.console.print(f"[blue][INFO][/blue] {message}")

    def success(self, message: str) -> None:
        """Print a success message."""
        self.console.print(f"[green][SUCCESS][/green] {message}")

    def warning(self, message: str) -> None:
        """Print a warning message."""
        self.console.print(f"[yellow][WARN][/yellow] {message}")

    def error(self, message: str) -> None:
        """Print an error message."""
        import os
        # Skip stderr output in MCP mode to avoid JSON-RPC interference
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            self.console.print(f"[red][ERROR][/red] {message}", style="red")

    def verbose_info(self, message: str) -> None:
        """Print a verbose info message if verbose mode is enabled."""
        if self.verbose:
            self.console.print(f"[cyan][DEBUG][/cyan] {message}")

    def startup_info(self, version: str, directory: str, database: str, config: Dict[str, Any]) -> None:
        """Display startup information in a styled panel."""
        info_table = Table.grid(padding=(0, 2))
        info_table.add_column(style="cyan")
        info_table.add_column()
        
        info_table.add_row("Version:", f"[green]{version}[/green]")
        info_table.add_row("Directory:", f"[blue]{directory}[/blue]")
        info_table.add_row("Database:", f"[magenta]{database}[/magenta]")
        
        # Add provider info if available
        if hasattr(config, 'embedding') and config.embedding:
            provider = config.embedding.provider
            model = getattr(config.embedding, 'model', 'default')
            info_table.add_row("Provider:", f"[yellow]{provider}[/yellow] ({model})")
        
        panel = Panel(
            info_table,
            title="[bold cyan]ChunkHound Indexing[/bold cyan]",
            border_style="cyan",
            padding=(1, 2)
        )
        self.console.print(panel)

    def create_progress_display(self) -> 'ProgressManager':
        """Create a modern progress display with multiple bars."""
        
        # Create custom text columns that handle missing fields gracefully
        def render_field(task, field_name, default="", style=""):
            try:
                return task.fields.get(field_name, default)
            except (AttributeError, KeyError):
                return default
        
        class SafeTextColumn(TextColumn):
            def __init__(self, field_name: str, default: str = "", style: str = "", justify: str = "left"):
                self.field_name = field_name
                self.default = default
                # Use a simple format string that we'll handle ourselves
                super().__init__("", style=style, justify=justify)
            
            def render(self, task):
                value = task.fields.get(self.field_name, self.default) if hasattr(task, 'fields') else self.default
                from rich.text import Text
                return Text(value, style=self.style)
        
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            SafeTextColumn("speed", "", style="green"),
            SafeTextColumn("info", "", style="dim"),
            console=self.console,
            expand=False,
            transient=False  # Don't make progress disappear when complete
        )
        
        return ProgressManager(progress, self.console)

    def completion_summary(self, stats: Dict[str, Any], processing_time: float) -> None:
        """Display completion summary in a styled panel."""
        # Create summary table
        summary_table = Table.grid(padding=(0, 2))
        summary_table.add_column(style="cyan")
        summary_table.add_column()
        
        summary_table.add_row("Processed:", f"[green]{stats.get('files_processed', 0)}[/green] files")
        summary_table.add_row("Skipped:", f"[yellow]{stats.get('files_skipped', 0)}[/yellow] files") 
        summary_table.add_row("Errors:", f"[red]{stats.get('files_errors', 0)}[/red] files")
        summary_table.add_row("Total chunks:", f"[blue]{stats.get('chunks_created', 0)}[/blue]")
        
        if 'embeddings_generated' in stats:
            summary_table.add_row("Embeddings:", f"[magenta]{stats['embeddings_generated']}[/magenta]")
        
        summary_table.add_row("Time:", f"[cyan]{processing_time:.2f}s[/cyan]")
        
        # Add cleanup stats if any
        if stats.get('cleanup_deleted_files', 0) > 0:
            summary_table.add_row("Cleaned files:", f"[yellow]{stats['cleanup_deleted_files']}[/yellow]")
        if stats.get('cleanup_deleted_chunks', 0) > 0:
            summary_table.add_row("Cleaned chunks:", f"[yellow]{stats['cleanup_deleted_chunks']}[/yellow]")
        
        panel = Panel(
            summary_table,
            title="[bold green]Processing Complete[/bold green]",
            border_style="green",
            padding=(1, 2)
        )
        self.console.print(panel)

    def initial_stats_panel(self, stats: Dict[str, Any]) -> None:
        """Display initial database statistics."""
        stats_table = Table.grid(padding=(0, 1))
        stats_table.add_column(style="dim")
        stats_table.add_column()
        
        stats_table.add_row("Files:", f"{stats.get('files', 0)}")
        stats_table.add_row("Chunks:", f"{stats.get('chunks', 0)}")
        stats_table.add_row("Embeddings:", f"{stats.get('embeddings', 0)}")
        
        self.console.print(f"[dim]Initial stats: {stats.get('files', 0)} files, {stats.get('chunks', 0)} chunks, {stats.get('embeddings', 0)} embeddings[/dim]")


class ProgressManager:
    """Manages multiple progress bars with Rich."""
    
    def __init__(self, progress: Progress, console: Console):
        self.progress = progress
        self.console = console
        self._tasks: Dict[str, TaskID] = {}
        self._live: Optional[Live] = None
    
    def __enter__(self) -> 'ProgressManager':
        self._live = Live(self.progress, console=self.console, refresh_per_second=10)
        self._live.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._live:
            self._live.stop()
    
    def add_task(
        self, 
        name: str, 
        description: str, 
        total: Optional[int] = None,
        speed: str = "",
        info: str = ""
    ) -> TaskID:
        """Add a new progress task."""
        task_id = self.progress.add_task(
            description, 
            total=total,
            speed=speed,
            info=info
        )
        self._tasks[name] = task_id
        return task_id
    
    def update_task(
        self, 
        name: str, 
        advance: int = 1, 
        description: Optional[str] = None,
        total: Optional[int] = None,
        speed: str = "",
        **fields
    ) -> None:
        """Update a progress task."""
        if name in self._tasks:
            update_kwargs = {"advance": advance}
            if description:
                update_kwargs["description"] = description
            if total is not None:
                update_kwargs["total"] = total
            if speed:
                fields["speed"] = speed
            if fields:
                update_kwargs.update(fields)
                
            self.progress.update(self._tasks[name], **update_kwargs)
    
    def get_task_id(self, name: str) -> Optional[TaskID]:
        """Get task ID by name."""
        return self._tasks.get(name)
    
    def finish_task(self, name: str) -> None:
        """Mark a task as finished."""
        if name in self._tasks:
            task_id = self._tasks[name]
            # Get current completed/total to set to 100%
            task = self.progress.tasks[task_id]
            if task.total:
                self.progress.update(task_id, completed=task.total)
    
    def add_subtask(
        self,
        parent_name: str,
        name: str,
        description: str,
        total: Optional[int] = None,
        indent_level: int = 1
    ) -> TaskID:
        """Add a subtask under a parent task with visual hierarchy."""
        # Create indented description for visual hierarchy
        indent = "  " + "└─ " if indent_level == 1 else "    " * indent_level + "└─ "
        task_id = self.progress.add_task(
            f"{indent}{description}",
            total=total,
            speed="",
            info=""
        )
        self._tasks[name] = task_id
        return task_id
    
    def get_progress_instance(self) -> Progress:
        """Get the underlying Progress instance for service layer use."""
        return self.progress


def format_stats(stats: Any) -> Dict[str, Any]:
    """Convert stats object to dictionary for display."""
    if hasattr(stats, '__dict__'):
        return stats.__dict__
    return stats if isinstance(stats, dict) else {}