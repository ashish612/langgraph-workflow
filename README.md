# BW-Auto: AI Communication Workflow

An intelligent LangGraph-based workflow that transforms informal messages into formal communications, automatically sending them via email and posting to Webex spaces.

## 🎯 What It Does

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                         BW-Auto Workflow                                      │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   ┌──────────────┐                                                            │
│   │ Input Message│                                                            │
│   │  "Hey, let's │                                                            │
│   │   reschedule │                                                            │
│   │  the meeting"│                                                            │
│   └──────┬───────┘                                                            │
│          │                                                                    │
│          ▼                                                                    │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                 │
│   │  Generate    │────▶│    Human     │────▶│  Send Email  │                 │
│   │ Formal Email │     │   Review     │     │  via SMTP    │                 │
│   │    (LLM)     │     │ ✓ Approve    │     │              │                 │
│   └──────────────┘     │ ✏ Edit       │     └──────┬───────┘                 │
│                        │ ✗ Reject     │            │                         │
│                        └──────────────┘            ▼                         │
│                               │            ┌──────────────┐                  │
│                               │            │   Generate   │                  │
│                               ▼            │ Webex Message│                  │
│                        ┌──────────────┐    │    (LLM)     │                  │
│                        │  Cancelled   │    └──────┬───────┘                  │
│                        │  (if reject) │           │                          │
│                        └──────────────┘           ▼                          │
│                                            ┌──────────────┐                  │
│                                            │  Post to     │                  │
│                                            │ Webex Space  │                  │
│                                            │ @mentions    │                  │
│                                            └──────────────┘                  │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

## ✨ Features

- **AI-Powered Transformation**: Uses Cisco Bridge API (GPT-4o-mini) to convert casual messages into professional communications
- **Human-in-the-Loop Review**: Review, edit, or reject emails before sending
- **Multi-Channel Delivery**: Sends via email AND posts to Webex
- **Smart Mentions**: Automatically @mentions specified team members in Webex
- **Workflow Orchestration**: Built on LangGraph with interrupt/resume support
- **Cisco OAuth2 Integration**: Secure authentication via Cisco's OAuth2 client credentials flow
- **Dry Run Mode**: Preview generated content without sending
- **Rich CLI**: Beautiful terminal interface with progress indicators

## 🚀 Quick Start

### 1. Installation

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file (or run `python main.py init`):

```bash
python main.py init
```

Then edit the `.env` file with your credentials:

```env
# Cisco Bridge API Configuration (LLM)
# Obtain these from your Cisco BridgeIT API access
CISCO_CLIENT_ID=your-cisco-client-id
CISCO_CLIENT_SECRET=your-cisco-client-secret
CISCO_APP_KEY=your-cisco-app-key

# Optional: LLM Parameters
LLM_TEMPERATURE=0.7

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
WEBEX_MENTION_EMAILS=person1@example.com,person2@example.com
```

### 3. Verify Configuration

```bash
python main.py check-config
```

### 4. Send a Message

```bash
# Basic usage (with human review)
python main.py send "We need to push tomorrow's standup to 3pm due to a conflict"

# Skip human review (auto-send)
python main.py send "Meeting postponed" --no-review

# Dry run (preview without sending)
python main.py send "Meeting postponed" --dry-run --verbose

# With custom sender name
python main.py send "Project deadline extended" --sender "John Smith"

# Override recipients
python main.py send "Update" --email-to "specific@example.com"
```

## 👤 Human-in-the-Loop Review

By default, the workflow pauses after generating the email so you can review it:

```
┌──────────────────────────────────────────────────────────────────┐
│ 📧 Generated Email - Please Review                              │
├──────────────────────────────────────────────────────────────────┤
│ To: recipient@example.com                                        │
│ Subject: Meeting Rescheduled to Thursday                         │
│ ──────────────────────────────────────────────────────────────── │
│                                                                  │
│ Dear Team,                                                       │
│                                                                  │
│ I hope this message finds you well. I am writing to inform...   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

Review Options:
  a - Approve and send
  e - Edit before sending  
  r - Reject and cancel

Your choice [a/e/r]:
```

### Review Options

| Option | Description |
|--------|-------------|
| **Approve (a)** | Send the email as-is and continue with Webex posting |
| **Edit (e)** | Modify the subject and/or body before sending |
| **Reject (r)** | Cancel the workflow without sending anything |

### Skip Review

If you trust the AI and want to send immediately:

```bash
python main.py send "Your message" --no-review
# or
python main.py send "Your message" -y
```

## 📖 Usage

### CLI Commands

```bash
# Send a message (with human review)
python main.py send "Your message here"

# Options:
#   --sender, -s       Name of the sender for signatures
#   --email-to, -e     Override email recipients (comma-separated)
#   --webex-room, -r   Override Webex room ID
#   --webex-mentions   Override Webex mentions (comma-separated emails)
#   --no-review, -y    Skip human review, send immediately
#   --dry-run, -d      Generate without sending
#   --verbose, -v      Show generated content

# Check configuration
python main.py check-config

# Initialize .env file
python main.py init
```

### Programmatic Usage

```python
from workflow import create_workflow
from config import get_settings

# Create workflow with human review enabled (default)
workflow = create_workflow()

# Run the workflow - will pause for review
result = workflow.run(
    message="Let's reschedule the sprint review to next Thursday",
    sender_name="Jane Doe",
    thread_id="my-workflow-123",
)

# Check if awaiting review
if result["status"] == "awaiting_review":
    print("Email generated, awaiting approval:")
    print(f"Subject: {result['formal_email_subject']}")
    print(f"Body: {result['formal_email_body']}")
    
    # Approve (with optional edits)
    result = workflow.approve_email(
        thread_id="my-workflow-123",
        edited_subject="Updated Subject",  # optional
    )
    
    # Or reject
    # result = workflow.reject_email(thread_id="my-workflow-123", reason="Not needed")

# Check final results
if result["status"] == "completed":
    print("Email sent:", result["email_sent"])
    print("Webex posted:", result["webex_posted"])

# Skip review entirely
result = workflow.run_without_review(
    message="Urgent: Server is back online",
    sender_name="Ops Team",
)
```

## 🔧 Configuration Details

### Cisco Bridge API Setup

The workflow uses Cisco's Bridge API to access GPT-4o-mini. To get your credentials:

1. Request access to Cisco BridgeIT API through your organization
2. Obtain your credentials:
   - **Client ID**: Your OAuth2 client identifier
   - **Client Secret**: Your OAuth2 client secret
   - **App Key**: Your BridgeIT application key
3. The system automatically handles OAuth2 token refresh

**How it works:**
```
┌─────────────┐    OAuth2     ┌──────────────┐
│   BW-Auto   │ ───────────▶  │  Cisco IDP   │
│   Workflow  │  ◀───────────  │  (Token)     │
└─────────────┘               └──────────────┘
       │
       │ Bearer Token
       ▼
┌──────────────────────────────────────────────┐
│  Cisco Bridge API (GPT-4o-mini)              │
│  https://chat-ai.cisco.com/openai/...        │
└──────────────────────────────────────────────┘
```

### Email Setup (Gmail Example)

1. Enable 2-Factor Authentication on your Google account
2. Generate an App Password:
   - Go to Google Account → Security → 2-Step Verification
   - Scroll to "App passwords"
   - Create a new app password for "Mail"
3. Use this app password in `SMTP_PASSWORD`

### Webex Setup

1. Create a Webex Bot at [developer.webex.com](https://developer.webex.com/my-apps/new)
2. Copy the Bot's access token
3. Add the bot to your Webex space
4. Get the room ID:
   - Use the Webex API: `GET https://webexapis.com/v1/rooms`
   - Or find it in the space details

## 📁 Project Structure

```
bw-auto/
├── main.py                   # CLI entry point
├── workflow.py               # LangGraph workflow definition
├── config.py                 # Configuration management
├── models.py                 # Data models and state
├── services/
│   ├── __init__.py
│   ├── cisco_bridge_llm.py   # Cisco Bridge API LLM wrapper
│   ├── email_service.py      # SMTP email service
│   └── webex_service.py      # Webex API service
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## 🔄 Workflow States

The workflow tracks state through these stages:

| Field | Description |
|-------|-------------|
| `original_message` | The input message |
| `formal_email_subject` | Generated email subject |
| `formal_email_body` | Generated email body |
| `webex_message` | Generated Webex message |
| `email_approved` | Whether email was approved by human reviewer |
| `email_rejected` | Whether email was rejected by human reviewer |
| `rejection_reason` | Reason for rejection (if applicable) |
| `email_sent` | Whether email was successfully sent |
| `webex_posted` | Whether Webex message was posted |
| `status` | Overall status: pending, in_progress, awaiting_review, completed, failed, cancelled |
| `errors` | List of any errors encountered |

## 🛠️ Development

### Running Tests

```bash
# Install dev dependencies
pip install pytest pytest-asyncio

# Run tests
pytest
```

### Extending the Workflow

To add new nodes to the workflow, edit `workflow.py`:

```python
def _build_graph(self) -> StateGraph:
    builder = StateGraph(WorkflowState)
    
    # Add your new node
    builder.add_node("my_new_step", self._my_new_step)
    
    # Update the flow
    builder.add_edge("post_to_webex", "my_new_step")
    builder.add_edge("my_new_step", END)
    
    return builder.compile()

def _my_new_step(self, state: WorkflowState) -> WorkflowState:
    # Your logic here
    return {**state, "my_field": "value"}
```

## 📝 License

MIT License - feel free to use and modify as needed.

