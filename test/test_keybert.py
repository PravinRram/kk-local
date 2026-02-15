from keybert import KeyBERT

# Removed age-based keywords
SEED_KEYWORDS = [
    "sports", "fitness", "health", "wellness",
    "food", "cooking", "dining",
    "arts", "crafts", "music", "dance", "culture",
    "games", "gaming", "technology", "digital",
    "nature", "outdoor", "gardening",
    "education", "learning", "workshop",
    "volunteering", "community", "social"
]

# Words to explicitly block if KeyBERT picks them up naturally
BLOCKED_KEYWORDS = {"seniors", "youth", "youths", "children", "family", "intergenerational", "ages", "age"}

doc = """
Take a pause and connect through stories at Heritage Story Circle: Memories Across Generations. This event invites youths and seniors to gather in a comfortable setting to share personal experiences, childhood memories, and reflections on how life in Singapore has changed over time.

Through guided prompts and open conversation, participants can listen, learn, and exchange perspectives in a respectful and welcoming space. Youths gain insight into lived histories, while seniors enjoy the opportunity to be heard and appreciated.

No preparation is needed — just bring your curiosity and willingness to listen.
"""
kw_model = KeyBERT()

print("--- Standard KeyBERT (No Seeds) ---")
keywords_standard = kw_model.extract_keywords(doc, keyphrase_ngram_range=(1, 1), stop_words='english', top_n=5)
print([k[0] for k in keywords_standard])

print("\n--- Hybrid KeyBERT (With Seed Keywords & Filters) ---")
keywords_seeded = kw_model.extract_keywords(
    doc, 
    keyphrase_ngram_range=(1, 1), 
    stop_words='english', 
    top_n=10, # Request more, then filter
    seed_keywords=SEED_KEYWORDS
)

# Filter and format tags
final_tags = []
for k in keywords_seeded:
    word = k[0].lower() # Force lowercase
    if word not in BLOCKED_KEYWORDS:
        final_tags.append(word)

# Deduplicate and take top 5
final_tags = list(set(final_tags))[:5]

print(f"Generated Tags: {final_tags}")
print("\nNote: These tags will appear in the 'Review' step and can be edited by the user.")
