import argparse
import requests

# API configurations
CROSSREF_API = "https://api.crossref.org/works"
GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"

def search_crossref(author, year, keyword):
    """Search Crossref API for works matching author, year and keyword"""
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
        return response.json()["message"]["items"]
    except requests.exceptions.RequestException as e:
        print(f"Error querying Crossref: {e}")
        return []

def search_google_books(author, year, keyword):
    """Search Google Books API for matching books"""
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
    
    args = parser.parse_args()
    
    # Parse citation
    try:
        author, year = args.citation.split(" (")
        year = int(year.strip(")"))
    except ValueError:
        print("Invalid citation format. Please use 'Author (Year)'")
        return
    
    # Search both APIs
    results = []
    print("Searching Crossref...")
    crossref_results = search_crossref(author, year, args.keyword)
    results.extend([(item, "crossref") for item in crossref_results])
    
    print("Searching Google Books...")
    google_results = search_google_books(author, year, args.keyword)
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
