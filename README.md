## 🚀 How to Run the Bot (After a Break)

Here’s how to restart the project if you come back to it after several days:

### 1. Activate the virtual environment

```bash
source venv/bin/activate
```

If it doesn’t exist yet, recreate it:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

### 2. Run the Slack bot

```bash
venv/bin/python app.py
```

This starts the Flask server that listens for Slack events on port 3000.

---

### 3. Start `ngrok` in a second terminal

```bash
ngrok http 3000
```

Copy the HTTPS URL (e.g. `https://abc1234.ngrok.io`).

Go to your Slack App → **Event Subscriptions** → update the **Request URL** to:

```
https://abc1234.ngrok.io/slack/events
```

---

### 4. Interact with the bot in Slack

Make sure the bot is invited to the public channel you're using:

```slack
/invite @YourBot
```

Then mention it with a prompt:

```slack
@YourBot give me 3 startup ideas for B2B tools
```

It will reply with startup ideas via the Groq-powered Mixtral model.

---

## 🔐 .env file example (keep this private!)

This file stores your secrets and tokens:

```
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_SIGNING_SECRET=your-slack-signing-secret
OPENROUTER_API_KEY=your-openrouter-key
```

---


## 📦 Optional: Freeze Dependencies

If you install new packages, save them by running:

```bash
pip freeze > requirements.txt
```