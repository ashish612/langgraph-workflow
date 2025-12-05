#!/usr/bin/env python3
"""
AI Communication Workflow - Main Entry Point

A LangGraph-based workflow that transforms messages into formal emails
and Webex messages, sending them to configured recipients.

Includes human-in-the-loop review for emails before sending.
"""

import typer
import uuid
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.syntax import Syntax
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = typer.Typer(
    name="bw-auto",
    help="AI-powered workflow to transform and send messages via Email and Webex",
    add_completion=False,
)
console = Console()


def display_email_for_review(subject: str, body: str, recipients: list) -> None:
    """Display the generated email for human review."""
    console.print()
    console.print(
        Panel(
            f"[bold cyan]To:[/bold cyan] {', '.join(recipients)}\n"
            f"[bold cyan]Subject:[/bold cyan] {subject}\n\n"
            f"{'─' * 50}\n\n"
            f"{body}",
            title="📧 Generated Email - Please Review",
            border_style="yellow",
            padding=(1, 2),
        )
    )
    console.print()


def edit_email_interactive(subject: str, body: str) -> tuple:
    """Allow interactive editing of email subject and body."""
    console.print("[bold]Edit Mode[/bold] (press Enter to keep current value)\n")

    # Edit subject
    new_subject = Prompt.ask(
        "[cyan]Subject[/cyan]",
        default=subject,
        show_default=True,
    )

    # For body, offer to open in editor or edit inline
    console.print(f"\n[dim]Current body:[/dim]\n{body[:200]}{'...' if len(body) > 200 else ''}\n")

    edit_body = Confirm.ask("Do you want to edit the email body?", default=False)

    if edit_body:
        console.print(
            "\n[yellow]Enter new body (type 'END' on a new line when done):[/yellow]"
        )
        lines = []
        while True:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        new_body = "\n".join(lines) if lines else body
    else:
        new_body = body

    return new_subject, new_body


def display_webex_for_review(message: str, room_id: str, mentions: list) -> None:
    """Display the generated Webex message for human review."""
    console.print()
    mentions_str = ", ".join(mentions) if mentions else "(none)"
    console.print(
        Panel(
            f"[bold cyan]Room ID:[/bold cyan] {room_id}\n"
            f"[bold cyan]Mentions:[/bold cyan] {mentions_str}\n\n"
            f"{'─' * 50}\n\n"
            f"{message}",
            title="💬 Generated Webex Message - Please Review",
            border_style="yellow",
            padding=(1, 2),
        )
    )
    console.print()


def edit_webex_interactive(message: str) -> str:
    """Allow interactive editing of Webex message."""
    console.print("[bold]Edit Mode[/bold]\n")

    # Show current message
    console.print(f"[dim]Current message:[/dim]\n{message[:300]}{'...' if len(message) > 300 else ''}\n")

    edit_msg = Confirm.ask("Do you want to edit the Webex message?", default=False)

    if edit_msg:
        console.print(
            "\n[yellow]Enter new message (type 'END' on a new line when done):[/yellow]"
        )
        lines = []
        while True:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        return "\n".join(lines) if lines else message
    else:
        return message


@app.command()
def send(
    message: str = typer.Argument(..., help="The message to transform and send"),
    sender: str = typer.Option(
        "Team Member", "--sender", "-s", help="Name of the sender for signatures"
    ),
    email_to: Optional[str] = typer.Option(
        None,
        "--email-to",
        "-e",
        help="Override email recipients (comma-separated)",
    ),
    webex_room: Optional[str] = typer.Option(
        None,
        "--webex-room",
        "-r",
        help="Override Webex room ID",
    ),
    webex_mentions: Optional[str] = typer.Option(
        None,
        "--webex-mentions",
        "-m",
        help="Override Webex mentions (comma-separated emails)",
    ),
    no_review: bool = typer.Option(
        False,
        "--no-review",
        "-y",
        help="Skip human review and send immediately",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-d",
        help="Generate messages but don't send them",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output including generated content",
    ),
):
    """
    Transform a message into a formal email and Webex message, then send both.

    By default, you'll review and approve the email before sending.
    Use --no-review to skip the review step.

    Examples:
        bw-auto send "We need to push the meeting to next week"
        bw-auto send "Project update" --no-review
        bw-auto send "Meeting postponed" --dry-run
    """
    from workflow import create_workflow
    from config import get_settings

    console.print(
        Panel.fit(
            "[bold cyan]AI Communication Workflow[/bold cyan]\n"
            "[dim]Transforming your message...[/dim]",
            border_style="cyan",
        )
    )

    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration Error:[/red] {str(e)}")
        console.print(
            "\n[yellow]Tip:[/yellow] Make sure you have a .env file with the required settings."
        )
        raise typer.Exit(1)

    # Parse optional overrides
    recipients = None
    if email_to:
        recipients = [e.strip() for e in email_to.split(",")]

    mentions = None
    if webex_mentions:
        mentions = [e.strip() for e in webex_mentions.split(",")]

    if dry_run:
        console.print("[yellow]Dry run mode - messages will not be sent[/yellow]\n")

    # Generate a unique thread ID for this workflow run
    thread_id = str(uuid.uuid4())

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Creating workflow...", total=None)

        # Create workflow with or without human review
        workflow = create_workflow(settings, enable_human_review=not no_review and not dry_run)

        if dry_run:
            # For dry run, we'll only generate the content
            progress.update(task, description="Generating email content...")

            from models import WorkflowState

            state: WorkflowState = {
                "original_message": message,
                "sender_name": sender,
                "email_recipients": recipients or settings.email_recipients,
                "webex_room_id": webex_room or settings.webex_room_id,
                "webex_mentions": mentions or settings.webex_mentions,
                "status": "pending",
                "errors": [],
            }

            # Generate email
            state = workflow._generate_email(state)
            progress.update(task, description="Generating Webex message...")

            # Generate Webex message
            state = workflow._generate_webex_message(state)
            progress.update(task, description="Done!")

            result = state
            result["email_sent"] = False
            result["webex_posted"] = False
            result["status"] = "dry_run"

        elif no_review:
            # Run without human review
            progress.update(task, description="Running workflow (no review)...")
            result = workflow.run_without_review(
                message=message,
                sender_name=sender,
                email_recipients=recipients,
                webex_room_id=webex_room,
                webex_mentions=mentions,
            )
            progress.update(task, description="Complete!")

        else:
            # Run with human review - will pause after email generation
            progress.update(task, description="Generating email for review...")
            result = workflow.run(
                message=message,
                sender_name=sender,
                email_recipients=recipients,
                webex_room_id=webex_room,
                webex_mentions=mentions,
                thread_id=thread_id,
            )
            progress.update(task, description="Email generated!")

    # Handle human review if workflow is paused
    # The workflow interrupts BEFORE review nodes run, so we check content and approval flags
    
    # === EMAIL REVIEW ===
    is_awaiting_email_review = (
        result.get("status") in ("in_progress", "awaiting_email_review", "awaiting_review")
        and result.get("formal_email_subject")
        and result.get("formal_email_body")
        and not result.get("email_approved")
        and not result.get("email_rejected")
    )
    if is_awaiting_email_review and not dry_run and not no_review:
        # Display email for review
        display_email_for_review(
            subject=result.get("formal_email_subject", ""),
            body=result.get("formal_email_body", ""),
            recipients=result.get("email_recipients", []),
        )

        # Review options
        console.print("[bold]Email Review Options:[/bold]")
        console.print("  [green]a[/green] - Approve and send")
        console.print("  [yellow]e[/yellow] - Edit before sending")
        console.print("  [red]r[/red] - Reject and cancel workflow")
        console.print()

        choice = Prompt.ask(
            "Your choice",
            choices=["a", "e", "r"],
            default="a",
        )

        if choice == "a":
            # Approve as-is
            console.print("\n[green]Approving email...[/green]")
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Sending email and generating Webex message...", total=None)
                result = workflow.approve_email(thread_id=thread_id)
                progress.update(task, description="Email sent, Webex message generated!")

        elif choice == "e":
            # Edit and approve
            new_subject, new_body = edit_email_interactive(
                subject=result.get("formal_email_subject", ""),
                body=result.get("formal_email_body", ""),
            )

            # Show preview of edits
            console.print("\n[bold]Updated Email Preview:[/bold]")
            display_email_for_review(
                subject=new_subject,
                body=new_body,
                recipients=result.get("email_recipients", []),
            )

            if Confirm.ask("Send this edited email?", default=True):
                console.print("\n[green]Sending edited email...[/green]")
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("Sending email and generating Webex message...", total=None)
                    result = workflow.approve_email(
                        thread_id=thread_id,
                        edited_subject=new_subject,
                        edited_body=new_body,
                    )
                    progress.update(task, description="Email sent, Webex message generated!")
            else:
                console.print("\n[yellow]Cancelled.[/yellow]")
                result = workflow.reject_email(thread_id=thread_id, reason="User cancelled after edit")

        else:
            # Reject
            reason = Prompt.ask(
                "Reason for rejection (optional)",
                default="",
            )
            result = workflow.reject_email(thread_id=thread_id, reason=reason or "User rejected")
            console.print("\n[yellow]Email rejected. Workflow cancelled.[/yellow]")

    # === WEBEX REVIEW ===
    is_awaiting_webex_review = (
        result.get("status") not in ("cancelled", "failed")
        and result.get("webex_message")
        and not result.get("webex_approved")
        and not result.get("webex_rejected")
        and result.get("email_approved")  # Only review Webex after email is approved
    )
    if is_awaiting_webex_review and not dry_run and not no_review:
        # Display Webex message for review
        display_webex_for_review(
            message=result.get("webex_message", ""),
            room_id=result.get("webex_room_id", ""),
            mentions=result.get("webex_mentions", []),
        )

        # Review options
        console.print("[bold]Webex Message Review Options:[/bold]")
        console.print("  [green]a[/green] - Approve and post")
        console.print("  [yellow]e[/yellow] - Edit before posting")
        console.print("  [red]r[/red] - Skip posting to Webex")
        console.print()

        choice = Prompt.ask(
            "Your choice",
            choices=["a", "e", "r"],
            default="a",
        )

        if choice == "a":
            # Approve as-is
            console.print("\n[green]Posting to Webex...[/green]")
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Posting message to Webex...", total=None)
                result = workflow.approve_webex(thread_id=thread_id)
                progress.update(task, description="Complete!")

        elif choice == "e":
            # Edit and approve
            new_message = edit_webex_interactive(
                message=result.get("webex_message", ""),
            )

            # Show preview of edits
            console.print("\n[bold]Updated Webex Message Preview:[/bold]")
            display_webex_for_review(
                message=new_message,
                room_id=result.get("webex_room_id", ""),
                mentions=result.get("webex_mentions", []),
            )

            if Confirm.ask("Post this edited message?", default=True):
                console.print("\n[green]Posting to Webex...[/green]")
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("Posting message to Webex...", total=None)
                    result = workflow.approve_webex(
                        thread_id=thread_id,
                        edited_message=new_message,
                    )
                    progress.update(task, description="Complete!")
            else:
                console.print("\n[yellow]Webex posting cancelled.[/yellow]")
                result = workflow.reject_webex(thread_id=thread_id, reason="User cancelled after edit")

        else:
            # Skip Webex
            reason = Prompt.ask(
                "Reason for skipping (optional)",
                default="",
            )
            result = workflow.reject_webex(thread_id=thread_id, reason=reason or "User skipped")
            console.print("\n[yellow]Webex posting skipped.[/yellow]")

    # Display results
    console.print()

    if verbose or dry_run:
        # Show generated email
        console.print(
            Panel(
                f"[bold]Subject:[/bold] {result.get('formal_email_subject', 'N/A')}\n\n"
                f"{result.get('formal_email_body', 'N/A')}",
                title="📧 Generated Email",
                border_style="blue",
            )
        )

        console.print()

        # Show generated Webex message
        webex_msg = result.get("webex_message", "N/A")
        if webex_msg and webex_msg != "N/A":
            console.print(
                Panel(
                    Markdown(webex_msg),
                    title="💬 Generated Webex Message",
                    border_style="green",
                )
            )
            console.print()

    # Status table
    table = Table(title="Workflow Results", show_header=True, header_style="bold")
    table.add_column("Channel", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details")

    # Email status
    status = result.get("status", "unknown")
    email_sent = result.get("email_sent", False)
    email_error = result.get("email_error")

    if dry_run:
        email_status = "[yellow]⏸ Skipped (dry run)[/yellow]"
    elif status == "cancelled":
        email_status = "[yellow]⏸ Cancelled[/yellow]"
    elif email_sent:
        email_status = "[green]✓ Sent[/green]"
    else:
        email_status = "[red]✗ Failed[/red]"

    if email_error:
        email_details = email_error
    elif status == "cancelled":
        email_details = result.get("rejection_reason", "User rejected")
    else:
        email_details = f"To: {', '.join(result.get('email_recipients', []))}"
    table.add_row("Email", email_status, email_details)

    # Webex status
    webex_posted = result.get("webex_posted", False)
    webex_error = result.get("webex_error")

    if dry_run:
        webex_status = "[yellow]⏸ Skipped (dry run)[/yellow]"
    elif status == "cancelled":
        webex_status = "[yellow]⏸ Cancelled[/yellow]"
    elif webex_posted:
        webex_status = "[green]✓ Posted[/green]"
    elif result.get("webex_message"):
        webex_status = "[red]✗ Failed[/red]"
    else:
        webex_status = "[dim]Not generated[/dim]"

    if webex_error:
        webex_details = webex_error
    elif status == "cancelled":
        webex_details = "Workflow cancelled"
    else:
        room_id = result.get("webex_room_id", "N/A")
        webex_details = f"Room: {room_id[:20]}..." if len(room_id) > 20 else f"Room: {room_id}"
    table.add_row("Webex", webex_status, webex_details)

    console.print(table)

    # Final status
    if status == "completed":
        console.print("\n[bold green]✓ Workflow completed successfully![/bold green]")
    elif status == "dry_run":
        console.print("\n[bold yellow]⏸ Dry run completed - no messages sent[/bold yellow]")
    elif status == "cancelled":
        console.print("\n[bold yellow]⏸ Workflow cancelled by user[/bold yellow]")
    elif status == "failed":
        console.print("\n[bold red]✗ Workflow failed[/bold red]")
        for error in result.get("errors", []):
            console.print(f"  [red]• {error}[/red]")
        raise typer.Exit(1)


@app.command()
def check_config():
    """
    Verify that all required configuration is present.
    """
    from config import get_settings

    console.print("[bold]Checking configuration...[/bold]\n")

    try:
        settings = get_settings()

        table = Table(title="Configuration Status", show_header=True)
        table.add_column("Setting", style="cyan")
        table.add_column("Status")
        table.add_column("Value")

        def mask_secret(value: str, show_last: int = 4) -> str:
            """Mask a secret value, showing only last N characters."""
            if not value:
                return "Not set"
            if len(value) <= show_last:
                return "****"
            return "****" + value[-show_last:]

        # Check each setting
        checks = [
            # Cisco Bridge API
            ("Cisco Client ID", bool(settings.cisco_client_id), mask_secret(settings.cisco_client_id, 8)),
            ("Cisco Client Secret", bool(settings.cisco_client_secret), mask_secret(settings.cisco_client_secret)),
            ("Cisco App Key", bool(settings.cisco_app_key), mask_secret(settings.cisco_app_key, 8)),
            ("Cisco Token URL", True, settings.cisco_token_url[:40] + "..." if len(settings.cisco_token_url) > 40 else settings.cisco_token_url),
            ("Cisco API URL", True, settings.cisco_api_url[:40] + "..." if len(settings.cisco_api_url) > 40 else settings.cisco_api_url),
            ("LLM Temperature", True, str(settings.llm_temperature)),
            # Email
            ("SMTP Host", bool(settings.smtp_host), settings.smtp_host),
            ("SMTP Port", bool(settings.smtp_port), str(settings.smtp_port)),
            ("SMTP Username", bool(settings.smtp_username), settings.smtp_username),
            ("SMTP Password", bool(settings.smtp_password), "****" if settings.smtp_password else "Not set"),
            ("Email From", bool(settings.email_from), settings.email_from),
            ("Email Recipients", bool(settings.email_recipients), ", ".join(settings.email_recipients)),
            # Webex
            ("Webex Token", bool(settings.webex_access_token), mask_secret(settings.webex_access_token)),
            ("Webex Room ID", bool(settings.webex_room_id), settings.webex_room_id[:20] + "..." if len(settings.webex_room_id) > 20 else settings.webex_room_id),
            ("Webex Mentions", True, ", ".join(settings.webex_mentions) if settings.webex_mentions else "(none)"),
        ]

        all_valid = True
        for name, valid, value in checks:
            status = "[green]✓[/green]" if valid else "[red]✗[/red]"
            if not valid:
                all_valid = False
            table.add_row(name, status, value)

        console.print(table)

        if all_valid:
            console.print("\n[green]All configuration is valid![/green]")
        else:
            console.print("\n[red]Some configuration is missing. Please check your .env file.[/red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Configuration Error:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command()
def init():
    """
    Create a sample .env file with all required configuration options.
    """
    env_content = """# Cisco Bridge API Configuration (LLM)
# Obtain these from your Cisco BridgeIT API access
CISCO_CLIENT_ID=your-cisco-client-id
CISCO_CLIENT_SECRET=your-cisco-client-secret
CISCO_APP_KEY=your-cisco-app-key

# Optional: Override default Cisco endpoints
# CISCO_TOKEN_URL=https://id.cisco.com/oauth2/default/v1/token
# CISCO_API_URL=https://chat-ai.cisco.com/openai/deployments/gpt-4o-mini/chat/completions

# LLM Parameters
LLM_TEMPERATURE=0.7
# LLM_MAX_TOKENS=1000

# Email Configuration (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password-here
EMAIL_FROM=your-email@gmail.com
EMAIL_TO=recipient1@example.com,recipient2@example.com

# Webex Configuration
WEBEX_ACCESS_TOKEN=your-webex-bot-token-here
WEBEX_ROOM_ID=your-webex-room-id-here
# Comma-separated list of people to mention (use email addresses)
WEBEX_MENTION_EMAILS=person1@example.com,person2@example.com
"""

    env_path = Path(".env")
    if env_path.exists():
        overwrite = typer.confirm(
            ".env file already exists. Overwrite?", default=False
        )
        if not overwrite:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    env_path.write_text(env_content)
    console.print("[green]Created .env file with sample configuration.[/green]")
    console.print("\nPlease edit the .env file with your actual credentials:")
    console.print("  1. Add your Cisco Bridge API credentials (client_id, client_secret, app_key)")
    console.print("  2. Configure SMTP settings for email")
    console.print("  3. Add your Webex bot token and room ID")
    console.print("\nThen run [bold]python main.py check-config[/bold] to verify.")


if __name__ == "__main__":
    app()
