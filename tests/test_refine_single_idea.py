import requests
import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

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
    return result["choices"][0]["message"]["content"]

def extract_ideas(text):
    """Extract numbered ideas from text, returning a list of (number, idea) tuples."""
    ideas = []
    for line in text.strip().split("\n"):
        if line.strip():
            parts = line.split(".", 1)
            if len(parts) == 2 and parts[0].strip().isdigit():
                ideas.append((int(parts[0].strip()), parts[1].strip()))
    return ideas

def test_refine_single_idea():
    # Original ideas
    original_text = """1. This app will present the child with a series of engaging mini-games, each featuring a handful of English words from the monthly list. The child's task will be to identify the English words they see or hear within the game, reinforcing their recognition and understanding of the words in a fun, interactive way.
2. The app will also include a feature where the child can explore a virtual world filled with interactive characters and objects, each associated with an English word from their studies. By clicking on these objects, the child will hear the English word and its Hebrew translation, helping them to connect the word with its meaning in a memorable and enjoyable way.
3. Additionally, the app will include a "Word of the Day" section, featuring a new English word each day accompanied by a fun animation or short video clip. The child can collect these words in a digital sticker book, reinforcing their memory of the word and its meaning and encouraging them to continue learning and exploring new English words each day."""

    # Extract ideas
    ideas = extract_ideas(original_text)
    print("Original ideas:", len(ideas))
    for num, idea in ideas:
        print(f"\nIdea {num}:")
        print(idea)

    # Test refining idea 2
    idea_to_refine = ideas[1][1]  # Get idea #2
    feedback = "the app gets as an input the works the parent want the kid to learn"

    prompt = f"""
You previously suggested this idea:

{idea_to_refine}

The founder gave feedback: "{feedback}"

Please revise ONLY this idea based on the feedback.
Use short, simple sentences.
Return just the revised version of this one idea.
Do not generate multiple ideas.
"""

    refined = call_openrouter(prompt).strip()
    print("\nRefined idea:")
    print(refined)

    # Verify the refined idea doesn't contain multiple ideas
    refined_ideas = extract_ideas(refined)
    print("\nNumber of ideas in refined response:", len(refined_ideas))
    if len(refined_ideas) > 1:
        print("❌ Error: Refined response contains multiple ideas!")
    else:
        print("✅ Success: Refined response contains single idea")

if __name__ == "__main__":
    test_refine_single_idea()
