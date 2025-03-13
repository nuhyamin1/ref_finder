import argparse
import requests
import json
import os
import hashlib
from datetime import datetime, timedelta

# API configurations
CROSSREF_API = "https://api.crossref.org/works"
GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"

# Cache functions
def get_cache_path():
    """Get the path to the cache directory"""
    cache_dir = os.path.join(os.path.expanduser("~"), ".ref_finder_cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def get_cached_results(query_hash):
    """Get cached results if they exist and are not expired"""
    cache_path = os.path.join(get_cache_path(), f"{query_hash}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)
            # Check if cache is expired (older than 1 day)
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cache_time < timedelta(days=1):
                print(f"Using cached results from {cache_time.strftime('%Y-%m-%d %H:%M:%S')}")
                return cache_data['results']
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Cache error: {e}. Fetching fresh data.")
    return None

def cache_results(query_hash, results):
    """Cache the results of a query"""
    cache_path = os.path.join(get_cache_path(), f"{query_hash}.json")
    cache_data = {
        'timestamp': datetime.now().isoformat(),
        'results': results
    }
    with open(cache_path, 'w') as f:
        json.dump(cache_data, f)

def generate_query_hash(author, year, keyword, source):
    """Generate a hash for the query to use as cache key"""
    query_string = f"{author}|{year}|{keyword}|{source}"
    return hashlib.md5(query_string.encode()).hexdigest()

def search_crossref(author, year, keyword, use_cache=True):
    """Search Crossref API for works matching author, year and keyword"""
    # Check cache first if use_cache is True
    query_hash = generate_query_hash(author, year, keyword, "crossref")
    if use_cache:
        cached_results = get_cached_results(query_hash)
        if cached_results is not None:
            return cached_results
    
    params = {
        "query.author": author,
        "query.bibliographic": keyword,
        "filter": f"from-pub-date:{year-1},until-pub-date:{year+1}",  # Expand year range
        "rows": 5,
        "sort": "relevance"
    }
    try:
        response = requests.get(CROSSREF_API, params=params)
        response.raise_for_status()
        results = response.json()["message"]["items"]
        # Cache the results
        cache_results(query_hash, results)
        return results
    except requests.exceptions.RequestException as e:
        print(f"Error querying Crossref: {e}")
        return []

def search_google_books(author, year, keyword, use_cache=True):
    """Search Google Books API for matching books"""
    # Check cache first if use_cache is True
    query_hash = generate_query_hash(author, year, keyword, "google_books")
    if use_cache:
        cached_results = get_cached_results(query_hash)
        if cached_results is not None:
            return cached_results
    
    query = f"inauthor:{author} subject:{keyword}"
    params = {
        "q": query,
        "maxResults": 5,
        "orderBy": "relevance"
    }
    try:
        response = requests.get(GOOGLE_BOOKS_API, params=params)
        response.raise_for_status()
        items = response.json().get("items", [])
        
        # Filter by publication year
        filtered_items = []
        for item in items:
            pub_date = item.get("volumeInfo", {}).get("publishedDate", "")
            if str(year) in pub_date:  # Check if year is in publication date
                filtered_items.append(item)
        
        # Cache the results
        cache_results(query_hash, filtered_items)
        return filtered_items
    except requests.exceptions.RequestException as e:
        print(f"Error querying Google Books: {e}")
        return []

def format_apa_reference(item, source):
    """Format a reference in APA style"""
    if source == "crossref":
        author_list = [f"{a['given']} {a['family']}" for a in item.get("author", [])]
        if len(author_list) > 1:
            authors = ", ".join(author_list[:-1]) + " & " + author_list[-1]
        else:
            authors = ", ".join(author_list)
        title = item.get("title", [""])[0]
        journal = item.get("container-title", [""])[0].title()
        year = item.get("issued", {}).get("date-parts", [[None]])[0][0]
        volume = item.get("volume", "")
        issue = item.get("issue", "")
        pages = item.get("page", "")
        doi = item.get("DOI", "")
        
        reference = f"{authors} ({year}). {title}. {journal}"
        if volume or issue:
            reference += f", {volume}"
            if issue:
                reference += f"({issue})"
        if pages:
            if "-" in pages:
                start, end = pages.split("-")
                reference += f", {start}–{end}"  # Use en dash for page ranges
            else:
                reference += f", {pages}"
        if doi:
            reference += f". https://doi.org/{doi}"
        else:
            reference += "."
    
    elif source == "google_books":
        volume_info = item.get("volumeInfo", {})
        authors = ", ".join(volume_info.get("authors", ["Unknown"]))
        title = volume_info.get("title", "")
        publisher = volume_info.get("publisher", "")
        year = volume_info.get("publishedDate", "")[:4]  # Get year from date
        isbn = volume_info.get("industryIdentifiers", [{}])[0].get("identifier", "")
        
        publisher = publisher or "Unknown publisher"
        reference = f"{authors} ({year}). {title}. {publisher}."
        if isbn:
            reference += f" ISBN: {isbn}"
    
    return reference

def main():
    parser = argparse.ArgumentParser(description="Find references in APA format")
    parser.add_argument("--citation", required=True, help="Citation in format 'Author (Year)'")
    parser.add_argument("--keyword", required=True, help="Keyword to search for")
    parser.add_argument("--no-cache", action="store_true", help="Bypass cache and fetch fresh data")
    
    args = parser.parse_args()
    
    # If no-cache flag is set, clear any existing cache for this search
    if args.no_cache:
        print("Cache bypass requested. Fetching fresh data...")
    
    # Parse citation
    try:
        author, year = args.citation.split(" (")
        year = int(year.strip(")"))
    except ValueError:
        print("Invalid citation format. Please use 'Author (Year)'")
        return
    
    # Search both APIs
    results = []
    use_cache = not args.no_cache
    
    print("Searching Crossref...")
    crossref_results = search_crossref(author, year, args.keyword, use_cache)
    results.extend([(item, "crossref") for item in crossref_results])
    
    print("Searching Google Books...")
    google_results = search_google_books(author, year, args.keyword, use_cache)
    results.extend([(item, "google_books") for item in google_results])
    
    if not results:
        print("\nNo references found matching your query")
        print("Try adjusting your search terms or expanding the year range")
        return
    
    # Format and display results
    print(f"\nFound {len(results)} references:")
    for item, source in results:
        print("\n" + format_apa_reference(item, source))

if __name__ == "__main__":
    main()
