from keybert import KeyBERT
from duckduckgo_search import DDGS

print("Initializing KeyBERT...")
kw_model = KeyBERT()
print("KeyBERT initialized.")

description = "Kampung Games Hour: Youth x Seniors"
print(f"Extracting keywords for: {description}")

keywords_list = kw_model.extract_keywords(
    description, 
    keyphrase_ngram_range=(1, 2), 
    stop_words='english', 
    top_n=3
)
print(f"Keywords: {keywords_list}")

search_terms = [k[0] for k in keywords_list]
query = " ".join(search_terms) + " event singapore"
print(f"Query: {query}")

print("Searching DDGS...")
try:
    with DDGS() as ddgs:
        results = list(ddgs.images(
            query, 
            region="sg-en", 
            safesearch="moderate", 
            max_results=5
        ))
        print(f"Found {len(results)} results.")
        if results:
            print(f"First result: {results[0]}")
except Exception as e:
    print(f"DDGS Error: {e}")
