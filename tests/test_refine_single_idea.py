import requests
import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

def call_openrouter(prompt):
    headers = {
        "Authorization": f"Bearer " + OPENROUTER_API_KEY,
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
    return result["choices"][0]["message"]["content"]

# Example idea and feedback
idea = """The app shows English words with images. 
The child must drag each word to the correct image. 
Correct matches earn points. 
Wrong ones show a hint."""

feedback = "Remove drag and drop. Use tapping. Make it more suitable for a 5-year-old."

# Construct a very clear, focused prompt
prompt = f"""
You previously suggested this idea:

{idea}

The founder gave feedback: "{feedback}"

Please revise ONLY this idea based on the feedback.
Use short, simple sentences.
Return just the revised version of this one idea.
Do not generate multiple ideas.
"""

print(call_openrouter(prompt))
