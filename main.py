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
RESEARCHER_SINGLE_IDEA_REFINEMENT_PROMPT_TEMPLATE = load_prompt("prompts/researcher_single_idea_refinement_prompt.txt")

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

@researcher_app.event("message")
def handle_message_events(body, logger):
    logger.info(body)
    # We don't need to do anything here, but we need to handle the event
    return

@researcher_app.event("app_mention")
def handle_researcher(event, say):
    print("DEBUG - Received event:", event)
    
    user_text = event["text"]
    thread_ts = event.get("thread_ts", event["ts"])

    # Handle refinement of a specific idea
    if "refine idea" in user_text.lower():
        try:
            print("DEBUG - Processing refine idea command")
            # Remove the bot mention from the text
            user_text = user_text.split(">", 1)[1].strip()
            
            # Split on the first colon
            raw = user_text.split(":", 1)
            if len(raw) < 2:
                raise ValueError("Invalid format")
                
            # Extract the idea number - look for the number after "refine idea"
            idea_part = raw[0].strip()
            idea_number = int(idea_part.split()[-1])  # Get the last word which should be the number
            feedback = raw[1].strip()

            previous = getattr(flask_app, "last_researcher_output", None)
            if not previous:
                say("⚠️ Sorry, I don't have anything to refine yet.")
                return

            print("DEBUG - Previous output:", previous)
            print("DEBUG - Idea number:", idea_number)
            print("DEBUG - Feedback:", feedback)

            # Extract ideas using the same function from the test
            ideas = []
            for line in previous.strip().split("\n"):
                if line.strip():
                    parts = line.split(".", 1)
                    if len(parts) == 2 and parts[0].strip().isdigit():
                        ideas.append((int(parts[0].strip()), parts[1].strip()))

            print("DEBUG - Extracted ideas:", ideas)

            # Find the idea to refine
            idea_to_refine = None
            for num, idea in ideas:
                if num == idea_number:
                    idea_to_refine = idea
                    break

            if not idea_to_refine:
                say("⚠️ Invalid idea number.")
                return

            print("DEBUG - Idea to refine:", idea_to_refine)

            # Use the prompt template
            prompt = RESEARCHER_SINGLE_IDEA_REFINEMENT_PROMPT_TEMPLATE.format(
                idea_to_refine=idea_to_refine,
                feedback=feedback
            )

            # Call OpenRouter with lower temperature
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            }
            
            body = {
                "model": "mistralai/mixtral-8x7b-instruct",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1  # Lower temperature for more focused output
            }
            
            print("DEBUG - Request body:", body)
            
            response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=body)
            result = response.json()
            
            print("DEBUG - Raw response:", result)
            
            refined = result["choices"][0]["message"]["content"].strip()
            
            print("DEBUG - Refined idea:", refined)

            # Update the idea in the list
            updated_ideas = []
            for num, idea in ideas:
                if num == idea_number:
                    updated_ideas.append((num, refined))
                else:
                    updated_ideas.append((num, idea))

            # Format the full response
            full_response = "\n".join([f"{num}. {idea}" for num, idea in updated_ideas])
            
            say(f"Here is the updated idea {idea_number}:", thread_ts=thread_ts)
            say(refined, thread_ts=thread_ts)
            flask_app.last_researcher_output = full_response
            return

        except Exception as e:
            print("DEBUG - Error:", str(e))
            say("⚠️ Couldn't parse the refine command. Please use 'refine idea 1: <your feedback>'.")
            return

    # Handle refinement of entire output
    if user_text.lower().startswith("refine:"):
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
    print("DEBUG - Setting last_researcher_output:", reply)
    flask_app.last_researcher_output = reply
    say(reply, thread_ts=thread_ts)
    return

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