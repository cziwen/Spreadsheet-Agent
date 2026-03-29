#!/usr/bin/env python3
"""Interactive chat interface for Spreadsheet Agent."""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

# Import from existing modules
from cli import _display_result, console
from agent.lead_agent import LeadAgent
from agent.core.llm_client import LLMClient


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Spreadsheet Agent - Interactive Chat Mode',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python chat.py                           # Use default workbook
  python chat.py --workbook data/my_data   # Use custom workbook
  python chat.py --no-banner               # Skip welcome banner
        """
    )
    parser.add_argument(
        '--workbook',
        default='data/demo_workbook',
        help='Path to workbook directory (default: data/demo_workbook)'
    )
    parser.add_argument(
        '--no-banner',
        action='store_true',
        help='Skip welcome banner'
    )
    return parser.parse_args()


def initialize_session(workbook_path):
    """Initialize agent session.

    Args:
        workbook_path: Path to workbook directory

    Returns:
        Initialized LeadAgent instance

    Raises:
        SystemExit: On fatal initialization errors
    """
    # Load environment variables
    load_dotenv()

    # Validate API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        rprint("[red]❌ Error: GOOGLE_API_KEY not set.[/red]")
        rprint("Please set your API key in .env file or environment variable.")
        sys.exit(1)

    # Validate workbook path
    workbook = Path(workbook_path)
    if not workbook.exists():
        rprint(f"[red]❌ Error: Workbook not found: {workbook_path}[/red]")
        rprint(f"Please create the directory or specify a valid path.")
        sys.exit(1)

    # Initialize components
    try:
        llm = LLMClient(api_key=api_key)
        lead_agent = LeadAgent(llm, workbook_path=workbook_path)
        return lead_agent
    except Exception as e:
        rprint(f"[red]❌ Fatal error initializing agent: {str(e)}[/red]")
        sys.exit(1)


def show_welcome(lead_agent, workbook_path):
    """Display welcome banner.

    Args:
        lead_agent: Initialized LeadAgent instance
        workbook_path: Path to workbook
    """
    tables = lead_agent.data_engine.list_tables()

    banner = f"""[bold cyan]Spreadsheet Agent - Chat Mode[/bold cyan]

[cyan]Workbook:[/cyan] {workbook_path}
[cyan]Tables loaded:[/cyan] {', '.join(tables) if tables else 'None'}

[yellow]Type your query or use commands:[/yellow]
  [bold]help[/bold]    - Show help
  [bold]tables[/bold]  - List available tables
  [bold]reload[/bold]  - Reload workbook data
  [bold]clear[/bold]   - Clear screen
  [bold]exit[/bold]    - Exit chat

[dim]Example queries:[/dim]
  • 统计订单表的订单总数和平均金额
  • 检查订单表的数据质量
  • 创建一个场景，订单金额增加10%"""

    console.print(Panel(banner, style="cyan", expand=False))


def show_help():
    """Display help message."""
    help_text = """[bold]Available Commands:[/bold]

  [cyan]exit, quit[/cyan]    Exit the chat session
  [cyan]help[/cyan]          Show this help message
  [cyan]clear[/cyan]         Clear the screen
  [cyan]reload[/cyan]        Reload workbook data from disk
  [cyan]tables[/cyan]        Show available tables and columns
  [cyan]history[/cyan]       Show recent queries (last 10)

[bold]Query Types:[/bold]

  [green]Cross-table analysis[/green]
    Join, filter, aggregate data across multiple tables
    Example: "Which customers have the highest lifetime value?"

  [green]Data quality[/green]
    Check for issues and get repair suggestions
    Example: "Check data quality in the orders table"

  [green]Scenarios[/green]
    Create what-if scenarios with data modifications
    Example: "Create scenario: increase order amounts by 15%"

  [green]Meta queries[/green]
    Ask what analyses are possible
    Example: "What kind of analysis is possible?"
"""
    console.print(Panel(help_text, title="Help", style="cyan", expand=False))


def show_tables(lead_agent):
    """Display available tables.

    Args:
        lead_agent: Initialized LeadAgent instance
    """
    tables = lead_agent.data_engine.list_tables()

    if not tables:
        rprint("[yellow]No tables found in workbook[/yellow]")
        return

    table = Table(title="Available Tables", style="cyan")
    table.add_column("Table Name", style="cyan")
    table.add_column("Rows", style="green")
    table.add_column("Columns", style="yellow")

    for table_name in tables:
        try:
            df = lead_agent.data_engine.get_table(table_name)
            # Show first 5 columns
            cols_str = ', '.join(df.columns.tolist()[:5])
            if len(df.columns) > 5:
                cols_str += f", ... +{len(df.columns) - 5} more"
            table.add_row(
                table_name,
                str(len(df)),
                cols_str
            )
        except Exception as e:
            table.add_row(table_name, "Error", str(e)[:30])

    console.print(table)


def show_history(lead_agent):
    """Display recent query history.

    Args:
        lead_agent: Initialized LeadAgent instance
    """
    if not hasattr(lead_agent.data_engine, 'history') or not lead_agent.data_engine.history:
        rprint("[yellow]⚠️  No history available[/yellow]")
        return

    history = lead_agent.data_engine.history[-10:]  # Last 10

    rprint("[cyan]Recent Queries (last 10):[/cyan]\n")
    for i, entry in enumerate(reversed(history), 1):
        query = entry.get('query', 'N/A')[:60]
        status = entry.get('status', 'unknown')
        status_color = 'green' if status == 'success' else 'red'
        rprint(f"  {i}. [{status_color}]{status}[/{status_color}] - {query}")


def handle_command(command, lead_agent, workbook_path):
    """Handle special commands.

    Args:
        command: User command
        lead_agent: Initialized LeadAgent instance
        workbook_path: Path to workbook

    Returns:
        True if command was handled, False if unknown command
    """
    cmd = command.strip().lower()

    if cmd in ['exit', 'quit']:
        rprint("\n👋 Goodbye! Session history saved.")
        sys.exit(0)

    elif cmd == 'help':
        show_help()
        return True

    elif cmd == 'clear':
        os.system('clear' if os.name != 'nt' else 'cls')
        return True

    elif cmd == 'reload':
        try:
            lead_agent.workbook = lead_agent.data_engine.load_workbook()
            rprint("[green]✓ Workbook reloaded[/green]")
        except Exception as e:
            rprint(f"[red]❌ Error reloading workbook: {str(e)}[/red]")
        return True

    elif cmd == 'tables':
        show_tables(lead_agent)
        return True

    elif cmd == 'history':
        show_history(lead_agent)
        return True

    else:
        return False


def chat_loop(lead_agent, workbook_path):
    """Main interactive chat loop.

    Args:
        lead_agent: Initialized LeadAgent instance
        workbook_path: Path to workbook
    """
    command_list = ['exit', 'quit', 'help', 'clear', 'reload', 'tables', 'history']

    try:
        while True:
            try:
                # Get user input
                user_input = input("\n>>> ").strip()

                # Skip empty input
                if not user_input:
                    continue

                # Handle commands
                if user_input.lower() in command_list:
                    handle_command(user_input, lead_agent, workbook_path)
                    continue

                # Process query
                try:
                    result = lead_agent.process_query(user_input)
                    _display_result(result)
                except KeyboardInterrupt:
                    rprint("\n[yellow]⚠️  Query interrupted[/yellow]")
                except EOFError:
                    rprint("\n\n👋 Goodbye! Session history saved.")
                    sys.exit(0)
                except Exception as e:
                    # Non-fatal error - continue session
                    rprint(f"[red]❌ Error: {str(e)}[/red]")
                    rprint("[dim]Session still active. Try another query or type 'help'.[/dim]")

            except EOFError:
                # Handle Ctrl+D at prompt
                rprint("\n\n👋 Goodbye! Session history saved.")
                sys.exit(0)

    except KeyboardInterrupt:
        # Handle Ctrl+C at prompt
        rprint("\n\n👋 Goodbye! Session history saved.")
        sys.exit(0)


def main():
    """Main entry point."""
    # Parse arguments
    args = parse_arguments()

    # Initialize session (exits on fatal error)
    lead_agent = initialize_session(args.workbook)

    # Show welcome banner
    if not args.no_banner:
        show_welcome(lead_agent, args.workbook)

    # Enter chat loop
    chat_loop(lead_agent, args.workbook)


if __name__ == "__main__":
    main()
