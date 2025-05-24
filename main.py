import os
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

load_dotenv()
flask_app = Flask(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# -------------------- Prompt Loading --------------------
def load_prompt(file_name):
    with open(file_name, "r") as f:
        return f.read()

RESEARCHER_PROMPT_TEMPLATE = load_prompt("prompts/researcher_prompt.txt")
RESEARCHER_PREPROCESSOR_PROMPT_TEMPLATE = load_prompt("prompts/researcher_preprocessor_prompt.txt")

# -------------------- Preprocessing --------------------
def preprocess_researcher_prompt(user_input):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    body = {
        "model": "mistralai/mixtral-8x7b-instruct",
        "messages": [
            {"role": "system", "content": RESEARCHER_PREPROCESSOR_PROMPT_TEMPLATE},
            {"role": "user", "content": user_input}
        ]
    }

    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=body)
    result = response.json()
    return result["choices"][0]["message"]["content"]

# -------------------- OpenRouter Call --------------------
def call_openrouter(prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    body = {
        "model": "mistralai/mixtral-8x7b-instruct",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=body)
    result = response.json()
    return result["choices"][0]["message"]["content"] if "choices" in result else "❌ Error generating response"

# -------------------- Researcher Bot --------------------
researcher_app = App(
    token=os.getenv("RESEARCHER_BOT_TOKEN"),
    signing_secret=os.getenv("RESEARCHER_SIGNING_SECRET")
)
researcher_handler = SlackRequestHandler(researcher_app)

@flask_app.route("/slack/researcher/events", methods=["POST"])
def researcher_events():
    if request.json and "challenge" in request.json:
        return jsonify({"challenge": request.json["challenge"]})
    return researcher_handler.handle(request)

@researcher_app.event("app_mention")
def handle_researcher(event, say):
    user_text = event["text"]
    thread_ts = event.get("thread_ts", event["ts"])

    # Handle refinement of entire output
    if user_text.lower().startswith("refine:") and not user_text.lower().startswith("refine idea"):
        feedback = user_text.replace("refine:", "").strip()
        previous = getattr(flask_app, "last_researcher_output", None)
        if not previous:
            say("⚠️ Sorry, I don't have anything to refine yet.")
            return

        prompt = f"""
You previously suggested these ideas:

{previous}

The founder responded with this feedback:

{feedback}

Please revise your original suggestions based on the feedback. Keep the same format and number the ideas clearly.
"""
        revised = call_openrouter(prompt)
        say(revised, thread_ts=thread_ts)
        flask_app.last_researcher_output = revised
        return

    # Handle refinement of a specific idea
    if user_text.lower().startswith("refine idea"):
        try:
            raw = user_text.strip().split(":", 1)
            if len(raw) < 2:
                raise ValueError("Invalid format")
            idea_number = int(raw[0].strip().split()[-1]) - 1
            feedback = raw[1].strip()

            previous = getattr(flask_app, "last_researcher_output", None)
            if not previous:
                say("⚠️ Sorry, I don't have anything to refine yet.")
                return

            ideas = [i.strip().split(".", 1)[-1].strip() for i in previous.strip().split("\n\n") if i.strip()]
            if idea_number < 0 or idea_number >= len(ideas):
                say("⚠️ Invalid idea number.")
                return

            selected_idea = ideas[idea_number]
            prompt = f"""
You previously suggested this idea:

{selected_idea}

The founder gave feedback: "{feedback}"

Please revise ONLY this idea based on the feedback.
Use short, simple sentences.
Return just the revised version of this one idea.
Do not generate multiple ideas or suggestions.
"""
            refined = call_openrouter(prompt).strip()
            ideas[idea_number] = refined
            full_response = "\n\n".join([f"{i+1}. {idea}" for i, idea in enumerate(ideas)])
            say(f"Here is the updated idea {idea_number+1}:", thread_ts=thread_ts)
            say(refined, thread_ts=thread_ts)
            flask_app.last_researcher_output = full_response
        except Exception as e:
            say("⚠️ Couldn't parse the refine command. Please use 'refine idea 1: <your feedback>'.")
        return

    # Handle proceed
    if user_text.lower().startswith("proceed:"):
        idea_number = user_text.replace("proceed:", "").strip()
        previous = getattr(flask_app, "last_researcher_output", None)
        if not previous:
            say("⚠️ Sorry, I don't have any ideas to proceed with.")
            return

        say(f"👍 Proceeding with idea {idea_number}. Next step would be to send this to the PM.", thread_ts=thread_ts)
        return

    # Default: new researcher request
    summary = preprocess_researcher_prompt(user_text)
    final_prompt = RESEARCHER_PROMPT_TEMPLATE.replace("{summary}", summary)
    reply = call_openrouter(final_prompt)
    say(reply, thread_ts=thread_ts)
    flask_app.last_researcher_output = reply

# -------------------- PM Bot --------------------
pm_app = App(
    token=os.getenv("PM_BOT_TOKEN"),
    signing_secret=os.getenv("PM_SIGNING_SECRET")
)
pm_handler = SlackRequestHandler(pm_app)

@flask_app.route("/slack/pm/events", methods=["POST"])
def pm_events():
    if request.json and "challenge" in request.json:
        return jsonify({"challenge": request.json["challenge"]})
    return pm_handler.handle(request)

@pm_app.event("app_mention")
def handle_pm(event, say):
    user_text = event["text"]
    thread_ts = event.get("thread_ts", event["ts"])

    pm_prompt = load_prompt("prompts/pm_prompt.txt").replace("{user_text}", user_text)
    reply = call_openrouter(pm_prompt)
    say(reply, thread_ts=thread_ts)

# -------------------- Main --------------------
if __name__ == "__main__":
    flask_app.run(port=3000)