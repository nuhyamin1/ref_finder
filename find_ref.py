import argparse
import requests
import json
import os
import hashlib
from datetime import datetime, timedelta
import csv
from io import StringIO
import sys

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
                print(f"Using cached results from {cache_time.strftime('%Y-%m-%d %H:%M:%S')}", file=sys.stderr)
                return cache_data['results']
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Cache error: {e}. Fetching fresh data.", file=sys.stderr)
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
    query_hash = generate_query_hash(author, year, keyword, "crossref")
    if use_cache:
        cached_results = get_cached_results(query_hash)
        if cached_results is not None:
            return cached_results
    
    params = {
        "query.author": author,
        "query.bibliographic": keyword,
        "filter": f"from-pub-date:{year-1},until-pub-date:{year+1}",
        "rows": 5,
        "sort": "relevance"
    }
    try:
        response = requests.get(CROSSREF_API, params=params)
        response.raise_for_status()
        results = response.json()["message"]["items"]
        cache_results(query_hash, results)
        return results
    except requests.exceptions.RequestException as e:
        print(f"Error querying Crossref: {e}", file=sys.stderr)
        return []

def search_google_books(author, year, keyword, use_cache=True):
    """Search Google Books API for matching books"""
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
        
        filtered_items = []
        for item in items:
            pub_date = item.get("volumeInfo", {}).get("publishedDate", "")
            if str(year) in pub_date:
                filtered_items.append(item)
        
        cache_results(query_hash, filtered_items)
        return filtered_items
    except requests.exceptions.RequestException as e:
        print(f"Error querying Google Books: {e}", file=sys.stderr)
        return []

def extract_metadata(item, source):
    """Extract metadata from API response item into a standardized format"""
    metadata = {'source': source}
    if source == "crossref":
        authors = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in item.get('author', [])]
        metadata['authors'] = authors
        metadata['title'] = item.get('title', [''])[0]
        metadata['journal'] = item.get('container-title', [''])[0]
        date_parts = item.get('issued', {}).get('date-parts', [[None]])[0]
        metadata['year'] = date_parts[0] if date_parts else None
        metadata['volume'] = item.get('volume', '')
        metadata['issue'] = item.get('issue', '')
        metadata['pages'] = item.get('page', '')
        metadata['doi'] = item.get('DOI', '')
        metadata['type'] = 'article'
    elif source == "google_books":
        volume_info = item.get('volumeInfo', {})
        authors = volume_info.get('authors', ['Unknown'])
        metadata['authors'] = authors
        metadata['title'] = volume_info.get('title', '')
        metadata['publisher'] = volume_info.get('publisher', 'Unknown publisher')
        published_date = volume_info.get('publishedDate', '')
        metadata['year'] = published_date[:4] if published_date else ''
        isbn = ''
        for identifier in volume_info.get('industryIdentifiers', []):
            if identifier.get('type') in ['ISBN_13', 'ISBN_10']:
                isbn = identifier.get('identifier', '')
                break
        metadata['isbn'] = isbn
        metadata['type'] = 'book'
    return metadata

def format_json(metadata_list):
    """Format results as JSON"""
    return json.dumps(metadata_list, indent=2, ensure_ascii=False)

def format_csv(metadata_list):
    """Format results as CSV"""
    fieldnames = ['type', 'authors', 'title', 'year', 'journal', 'volume', 'issue', 'pages', 'doi', 'publisher', 'isbn', 'source']
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    
    for entry in metadata_list:
        entry_copy = entry.copy()
        entry_copy['authors'] = ', '.join(entry_copy.get('authors', []))
        writer.writerow(entry_copy)
    
    return output.getvalue()

def generate_bibtex_key(entry):
    """Generate a unique BibTeX citation key"""
    authors = entry.get('authors', [])
    if authors:
        first_author_last = authors[0].split()[-1]
    else:
        first_author_last = 'Unknown'
    year = entry.get('year', '') or '0000'
    title_word = entry.get('title', 'untitled').split()[0]
    return f"{first_author_last}{year}{title_word}".lower()

def format_bibtex(metadata_list):
    """Format results as BibTeX"""
    entries = []
    for entry in metadata_list:
        entry_type = entry['type']
        key = generate_bibtex_key(entry)
        fields = []
        
        authors = ' and '.join(entry.get('authors', []))
        if authors:
            fields.append(f"  author = {{{authors}}}")
        
        if entry.get('title'):
            fields.append(f"  title = {{{entry['title']}}}")
        
        if entry.get('year'):
            fields.append(f"  year = {{{entry['year']}}}")
        
        if entry_type == 'article':
            if entry.get('journal'):
                fields.append(f"  journal = {{{entry['journal']}}}")
            if entry.get('volume'):
                fields.append(f"  volume = {{{entry['volume']}}}")
            if entry.get('issue'):
                fields.append(f"  number = {{{entry['issue']}}}")
            if entry.get('pages'):
                fields.append(f"  pages = {{{entry['pages']}}}")
            if entry.get('doi'):
                fields.append(f"  doi = {{{entry['doi']}}}")
        elif entry_type == 'book':
            if entry.get('publisher'):
                fields.append(f"  publisher = {{{entry['publisher']}}}")
            if entry.get('isbn'):
                fields.append(f"  isbn = {{{entry['isbn']}}}")
        
        entries.append(f"@{entry_type}{{{key},\n" + ",\n".join(fields) + "\n}")
    
    return "\n\n".join(entries)

def format_apa_from_metadata(metadata):
    """Format a reference in APA style from metadata"""
    if metadata['type'] == 'article':
        authors = metadata.get('authors', [])
        authors_str = _format_author_list(authors)
        
        title = metadata.get('title', '').rstrip('. ')
        if title and title[-1] not in {'.', '?', '!'}:
            title += '.'
            
        reference = f"{authors_str} ({metadata.get('year', '')}). {title}"
        
        # Journal handling
        if journal := metadata.get('journal', ''):
            reference += f" {journal}"
        
        # Volume/issue handling
        volume = metadata.get('volume', '')
        issue = metadata.get('issue', '')
        if volume or issue:
            reference += f", {volume}"
            if issue:
                reference += f"({issue})"
        
        # Pages handling
        if pages := metadata.get('pages', ''):
            reference += f", {pages.replace('-', '–')}"
        
        # DOI handling
        if doi := metadata.get('doi', ''):
            if not reference.endswith(('.', '?', '!')):
                reference += '.'
            reference += f" https://doi.org/{doi}"
        else:
            if not reference.endswith('.'):
                reference += '.'
        
        return reference
    
    elif metadata['type'] == 'book':
        # Similar improved logic for books
        authors = metadata.get('authors', [])
        authors_str = _format_author_list(authors)
        
        title = metadata.get('title', '').rstrip('. ')
        if title and title[-1] not in {'.', '?', '!'}:
            title += '.'
        
        reference = f"{authors_str} ({metadata.get('year', '')}). {title}"
        
        if publisher := metadata.get('publisher', ''):
            reference += f" {publisher}."
        
        if isbn := metadata.get('isbn', ''):
            reference += f" ISBN: {isbn}"
        
        return reference
    
def _format_author_list(authors):
    """Helper to format author list"""
    if not authors:
        return ""
    if len(authors) > 1:
        return ", ".join(authors[:-1]) + " & " + authors[-1]
    return authors[0]

def main():
    parser = argparse.ArgumentParser(description="Find references in multiple formats")
    parser.add_argument("--citation", required=True, help="Citation in format 'Author (Year)'")
    parser.add_argument("--keyword", required=True, help="Keyword to search for")
    parser.add_argument("--no-cache", action="store_true", help="Bypass cache and fetch fresh data")
    parser.add_argument("--format", choices=['text', 'json', 'csv', 'bibtex'], 
                        default='text', help="Output format (default: text)")
    parser.add_argument("--save", type=str, help="Path to save the output file")
    
    args = parser.parse_args()
    
    # Parse citation
    try:
        author, rest = args.citation.split(" (", 1)
        year = int(rest.strip(")"))
    except ValueError:
        print("Invalid citation format. Please use 'Author (Year)'", file=sys.stderr)
        return
    
    # Search both APIs
    results = []
    use_cache = not args.no_cache
    
    print("Searching Crossref...", file=sys.stderr)
    crossref_results = search_crossref(author, year, args.keyword, use_cache)
    results.extend([(item, "crossref") for item in crossref_results])
    
    print("Searching Google Books...", file=sys.stderr)
    google_results = search_google_books(author, year, args.keyword, use_cache)
    results.extend([(item, "google_books") for item in google_results])
    
    if not results:
        print("\nNo references found matching your query", file=sys.stderr)
        print("Try adjusting your search terms or expanding the year range", file=sys.stderr)
        return
    
    # Extract metadata
    metadata_list = [extract_metadata(item, source) for item, source in results]
    
    # Generate output
    if args.format == 'json':
        output = format_json(metadata_list)
    elif args.format == 'csv':
        output = format_csv(metadata_list)
    elif args.format == 'bibtex':
        output = format_bibtex(metadata_list)
    else:  # text format
        apa_references = [format_apa_from_metadata(md) for md in metadata_list]
        output = '\n\n'.join(apa_references)
    
    # Save or print output
    if args.save:
        with open(args.save, 'w') as f:
            f.write(output)
        print(f"\nOutput saved to {args.save}", file=sys.stderr)
    else:
        print(output)

if __name__ == "__main__":
    main()