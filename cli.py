"""CLI interface for Spreadsheet Agent."""

import os
import json
import typer
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from agent.lead_agent import LeadAgent
from agent.core.llm_client import LLMClient

# Load environment variables
load_dotenv()

app = typer.Typer(help="Spreadsheet Agent - AI-powered spreadsheet analysis")
console = Console()


@app.command()
def query(
    q: str = typer.Argument(..., help="Natural language query"),
    workbook: str = typer.Option("data/demo_workbook", help="Path to workbook directory"),
):
    """Execute a natural language query on the spreadsheet."""
    try:
        # Initialize LLM client
        api_key = os.getenv("GOOGLE_API_KEY")

        if not api_key:
            rprint(
                "[red]❌ Error: GOOGLE_API_KEY not set.[/red]\n"
                "Please set your API key in .env file or environment variable."
            )
            raise typer.Exit(code=1)

        llm = LLMClient(api_key=api_key)

        # Initialize lead agent
        lead_agent = LeadAgent(llm, workbook_path=workbook)

        # Process query
        result = lead_agent.process_query(q)

        # Display results
        _display_result(result)

    except Exception as e:
        rprint(f"[red]❌ Error: {str(e)}[/red]")
        raise typer.Exit(code=1)


@app.command()
def load_data(
    workbook: str = typer.Option("data/demo_workbook", help="Path to workbook directory"),
):
    """Load and display workbook tables."""
    try:
        from agent.core.data_engine import DataEngine

        console.print("[bold cyan]Loading workbook...[/bold cyan]\n")

        data_engine = DataEngine(workbook_path=workbook)
        tables = data_engine.load_workbook()

        if not tables:
            rprint("[yellow]⚠️  No tables found in workbook[/yellow]")
            return

        for table_name, df in tables.items():
            console.print(f"[bold green]📊 Table: {table_name}[/bold green]")
            console.print(f"   Rows: {len(df)}, Columns: {len(df.columns)}")
            console.print(f"   Columns: {', '.join(df.columns.tolist())}\n")

            # Show sample data
            if len(df) > 0:
                table = Table(title=f"{table_name} - Sample Data")

                for col in df.columns:
                    table.add_column(col)

                for _, row in df.head(3).iterrows():
                    table.add_row(*[str(val)[:20] for val in row])

                console.print(table)
                console.print()

    except Exception as e:
        rprint(f"[red]❌ Error: {str(e)}[/red]")
        raise typer.Exit(code=1)


@app.command()
def scenarios(
    workbook: str = typer.Option("data/demo_workbook", help="Path to workbook directory"),
):
    """List all saved scenarios."""
    try:
        from agent.core.data_engine import DataEngine

        console.print("[bold cyan]Loading scenarios...[/bold cyan]\n")

        data_engine = DataEngine(workbook_path=workbook)
        scenarios = data_engine.load_scenarios()

        if not scenarios:
            rprint("[yellow]⚠️  No scenarios found[/yellow]")
            return

        for scenario_name, scenario_data in scenarios.items():
            console.print(f"[bold green]🎬 Scenario: {scenario_name}[/bold green]")
            console.print(f"   Created: {scenario_data.get('created_at', 'N/A')}")

            params = scenario_data.get("parameters", {})
            if params:
                console.print(f"   Parameters: {json.dumps(params, indent=4)}")

            console.print()

    except Exception as e:
        rprint(f"[red]❌ Error: {str(e)}[/red]")
        raise typer.Exit(code=1)


def _display_result(result: dict):
    """Display result based on query type.

    Args:
        result: Result dictionary from agent
    """
    result_type = result.get("type", "unknown")

    if result_type == "error":
        rprint(f"[red]❌ Error: {result.get('error', 'Unknown error')}[/red]")
        return

    if result_type == "meta":
        _display_meta_result(result)

    elif result_type == "cross_table":
        _display_cross_table_result(result)

    elif result_type == "quality":
        _display_quality_result(result)

    elif result_type == "scenario":
        _display_scenario_result(result)

    else:
        rprint(f"[yellow]Unknown result type: {result_type}[/yellow]")


def _display_meta_result(result: dict):
    """Display meta/capability query result."""
    rprint(f"[bold cyan]💡 Analysis Capabilities[/bold cyan]\n")

    response = result.get("result")
    if response:
        rprint(response)
    else:
        error = result.get("error")
        if error:
            rprint(f"[red]Error: {error}[/red]")
        else:
            rprint("[yellow]No response available[/yellow]")


def _display_cross_table_result(result: dict):
    """Display cross-table analysis result."""
    rprint(f"[bold green]✓ Cross-Table Analysis Complete[/bold green]")

    rprint(f"[cyan]Tables used:[/cyan] {', '.join(result.get('tables_used', []))}")

    # Display relationships
    relationships = result.get("relationships", [])
    if relationships:
        rprint(f"[cyan]Relationships found:[/cyan]")
        for rel in relationships:
            # Handle both join_keys (list) and join_key (string) formats
            join_keys = rel.get("join_keys", [])
            if join_keys and len(join_keys) > 0:
                left_col, right_col = join_keys[0]
                rprint(
                    f"  • {rel['left_table']}.{left_col} = {rel['right_table']}.{right_col}"
                    f" (overlap: {rel.get('overlap_count', 0)})"
                )
            else:
                # Fallback for join_key format
                join_key = rel.get("join_key")
                if join_key:
                    rprint(
                        f"  • {rel['left_table']}.{join_key} = {rel['right_table']}.{join_key}"
                        f" (overlap: {rel.get('overlap_count', 0)})"
                    )

    # Display result dataframe
    result_df = result.get("result")

    if result_df is not None and len(result_df) > 0:
        rprint(f"\n[cyan]Query Results:[/cyan] ({len(result_df)} rows)")

        table = Table(title="Results")

        for col in result_df.columns[:10]:  # Limit to 10 columns
            table.add_column(col, style="cyan")

        for idx, row in result_df.head(10).iterrows():
            table.add_row(*[str(val)[:30] for val in row][:10])

        console.print(table)
    else:
        rprint("[yellow]No results returned[/yellow]")


def _display_quality_result(result: dict):
    """Display data quality result."""
    rprint(f"[bold green]✓ Data Quality Scan Complete[/bold green]")

    rprint(f"[cyan]Table:[/cyan] {result.get('table', 'N/A')}")
    rprint(
        f"[cyan]Size:[/cyan] {result.get('total_rows', 0)} rows × {result.get('total_columns', 0)} columns"
    )

    quality_score = result.get("quality_score", 0)
    if quality_score >= 80:
        score_color = "green"
    elif quality_score >= 60:
        score_color = "yellow"
    else:
        score_color = "red"

    rprint(f"[{score_color}]Quality Score: {quality_score:.0f}/100[/{score_color}]\n")

    # Display issues
    issues = result.get("issues", [])

    if issues:
        rprint(f"[cyan]Issues Found: {result.get('total_issues', 0)}[/cyan]\n")

        for i, issue in enumerate(issues[:10], 1):
            severity_color = {"high": "red", "medium": "yellow", "low": "blue"}.get(
                issue.get("severity", "low"), "blue"
            )

            rprint(
                f"  {i}. [{severity_color}]{issue.get('type', 'unknown').upper()}[/{severity_color}] "
                f"{issue.get('description', 'N/A')}"
            )

    # Display repair suggestions
    repairs = result.get("repairs", [])

    if repairs:
        rprint(f"\n[cyan]Suggested Repairs:[/cyan]\n")

        for i, repair in enumerate(repairs[:5], 1):
            action = repair.get("action", "Unknown")
            confidence = repair.get("confidence", 0)

            rprint(
                f"  {i}. {action} "
                f"([{'green' if confidence > 0.7 else 'yellow'}]{confidence:.0%}[/])"
            )


def _format_table_for_display(table_str: str, max_rows: int = 10) -> str:
    """Format DataFrame string representation as readable table.

    Args:
        table_str: String representation of DataFrame
        max_rows: Maximum rows to display

    Returns:
        Formatted table string
    """
    if not table_str:
        return "No table data"

    lines = table_str.strip().split('\n')

    # Show header and first N rows
    display_lines = lines[:max_rows + 1]  # +1 for header

    if len(lines) > max_rows + 1:
        display_lines.append(f"... and {len(lines) - max_rows - 1} more rows")

    return '\n'.join(display_lines)


def _display_scenario_result(result: dict):
    """Display scenario result."""
    operation = result.get("operation", "unknown")

    if operation == "create":
        rprint(f"\n[bold green]✓ Scenario Created[/bold green]")

        scenario_name = result.get('scenario_name', 'N/A')
        rprint(f"[cyan]Name:[/cyan] {scenario_name}")

        params = result.get("parameters", {})
        if params:
            rprint(f"\n[cyan]Parameters Applied:[/cyan]")
            for key, value in params.items():
                is_increase = "increase" in key.lower()
                direction = "increase" if is_increase else "decrease"
                rprint(f"  • {key}: {value}% {direction}")

        metrics = result.get("metrics", {})
        if metrics:
            rprint(f"\n[cyan]Impact Summary:[/cyan]")
            for table, table_metrics in metrics.items():
                rprint(f"  {table}:")
                for col, metric_data in table_metrics.items():
                    if isinstance(metric_data, dict) and "baseline" in metric_data:
                        # Before/after format with comparison
                        baseline = metric_data.get("baseline", 0)
                        scenario = metric_data.get("scenario", 0)
                        change = metric_data.get("change", 0)
                        change_pct = metric_data.get("change_pct", 0)

                        # Color code based on change direction
                        change_color = "green" if change > 0 else "red" if change < 0 else "yellow"
                        rprint(f"    • {col}: {baseline:.2f} → {scenario:.2f} "
                              f"([{change_color}]{change:+.2f} / {change_pct:+.1f}%[/])")
                    else:
                        # Legacy format (just sum)
                        rprint(f"    • {col}: {metric_data:.2f}")

        # Show file location and description
        rprint(f"\n📁 [cyan]Saved to:[/cyan] data/demo_workbook/scenarios/{scenario_name}.json")
        rprint(f"\n[dim]What the scenario does:[/dim]")
        summary = result.get("summary", "")
        if summary:
            # Format summary nicely with indentation
            for line in summary.split("\n"):
                rprint(f"  {line}")

        # Show preview of modified tables
        tables = result.get("tables", {})
        if tables:
            rprint(f"\n[dim]Modified data preview (first 5 rows):[/dim]")
            for table_name, table_data in tables.items():
                rprint(f"\n[yellow]📊 {table_name}[/yellow]")
                formatted = _format_table_for_display(table_data, max_rows=5)
                # Use code block for better formatting
                rprint(f"[dim cyan]{formatted}[/dim cyan]")
            rprint(f"\n[dim]💡 Tip: Full table data saved in JSON file[/dim]")

    elif operation == "compare":
        rprint(f"[bold green]✓ Scenario Comparison Complete[/bold green]")

        scenarios = result.get("scenarios_compared", [])
        rprint(f"[cyan]Scenarios compared:[/cyan] {', '.join(scenarios)}\n")

        comparison = result.get("comparison", {})
        differences = comparison.get("differences", {})

        if differences:
            rprint(f"[cyan]Key Differences:[/cyan]\n")

            for table_name, diffs in differences.items():
                rprint(f"  {table_name}:")

                for metric_name, diff_info in diffs.items():
                    pct_change = diff_info.get("percentage", 0)
                    pct_color = "green" if pct_change < 0 else "red"

                    rprint(
                        f"    • {metric_name}: "
                        f"[{pct_color}]{pct_change:+.1f}%[/{pct_color}]"
                    )

    elif operation == "list":
        rprint(f"[bold green]✓ Scenarios List[/bold green]")

        scenarios = result.get("scenarios", [])
        total = result.get("total", 0)

        rprint(f"[cyan]Total scenarios: {total}[/cyan]\n")

        if scenarios:
            table = Table(title="Saved Scenarios")
            table.add_column("Name", style="cyan")
            table.add_column("Created", style="green")
            table.add_column("Base", style="yellow")

            for scenario in scenarios:
                table.add_row(
                    scenario.get("name", "N/A"),
                    scenario.get("created_at", "N/A")[:19],
                    scenario.get("base_scenario", "N/A"),
                )

            console.print(table)


if __name__ == "__main__":
    app()
