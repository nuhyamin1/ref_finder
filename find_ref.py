import argparse
import requests
import json
import os
import hashlib
from datetime import datetime, timedelta
import csv
from io import StringIO
import sys
import time

# API configurations
CROSSREF_API = "https://api.crossref.org/works"
GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
OPEN_LIBRARY_API = "https://openlibrary.org/search.json"

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
        "filter": f"from-pub-date:{year-1},until-pub-date:{year+1}",
        "rows": 5,
        "sort": "relevance"
    }
    
    # Only add keyword to search if provided
    if keyword:
        keyword_query = ' '.join([f'"{term}"' if ' ' in term else term for term in keyword.split()])
        params["query.bibliographic"] = keyword_query
    
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
    
    # Handle multi-word phrases in keyword search
    keyword_parts = [f'"{term}"' if ' ' in term else term for term in keyword.split()]
    keyword_query = ' '.join(keyword_parts)
    query = f"inauthor:{author} subject:{keyword_query}"
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

def search_semantic_scholar(author, year, keyword, use_cache=True):
    """Search Semantic Scholar API for academic papers"""
    query_hash = generate_query_hash(author, year, keyword, "semantic_scholar")
    if use_cache:
        cached_results = get_cached_results(query_hash)
        if cached_results is not None:
            return cached_results
    
    # Construct query with author and keyword
    query = author if not keyword else f"{author} {keyword}"
    params = {
        "query": query,
        "limit": 5,
        "fields": "title,authors,year,journal,venue,url,externalIds"
    }
    
    headers = {
        "User-Agent": "Reference-Manager/1.0"  # Adding a user agent to be more polite
    }
    
    try:
        response = requests.get(SEMANTIC_SCHOLAR_API, params=params, headers=headers)
        response.raise_for_status()
        items = response.json().get("data", [])
        
        # Filter by year (±1 year)
        filtered_items = []
        for item in items:
            item_year = item.get("year")
            if item_year and (year-1 <= item_year <= year+1):
                filtered_items.append(item)
        
        cache_results(query_hash, filtered_items)
        return filtered_items
    except requests.exceptions.RequestException as e:
        print(f"Error querying Semantic Scholar: {e}", file=sys.stderr)
        # Sleep for a moment if rate limited
        if "429" in str(e):
            print("Rate limited by Semantic Scholar API. Using cached results if available.", file=sys.stderr)
            time.sleep(2)  # Add a small delay
        return []

def search_open_library(author, year, keyword, use_cache=True):
    """Search Open Library API for books"""
    query_hash = generate_query_hash(author, year, keyword, "open_library")
    if use_cache:
        cached_results = get_cached_results(query_hash)
        if cached_results is not None:
            return cached_results
    
    # Construct query
    query = f"author:{author} {keyword}"
    params = {
        "q": query,
        "limit": 5
    }
    
    try:
        response = requests.get(OPEN_LIBRARY_API, params=params)
        response.raise_for_status()
        docs = response.json().get("docs", [])
        
        # Filter by year
        filtered_items = []
        for item in docs:
            pub_year = item.get("first_publish_year")
            if pub_year and (year-1 <= pub_year <= year+1):
                filtered_items.append(item)
        
        cache_results(query_hash, filtered_items)
        return filtered_items
    except requests.exceptions.RequestException as e:
        print(f"Error querying Open Library: {e}", file=sys.stderr)
        return []

def extract_metadata(item, source):
    """Extract metadata from API response item into a standardized format"""
    metadata = {'source': source}
    if source == "crossref":
        # Existing crossref code
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
        # Existing google_books code
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
    elif source == "semantic_scholar":
        # Add semantic scholar metadata extraction
        authors = [author.get('name', '') for author in item.get('authors', [])]
        metadata['authors'] = authors
        metadata['title'] = item.get('title', '')
        metadata['journal'] = item.get('venue', '') or item.get('journal', {}).get('name', '')
        metadata['year'] = item.get('year')
        metadata['doi'] = item.get('externalIds', {}).get('DOI', '')
        metadata['url'] = item.get('url', '')
        metadata['type'] = 'article'
    elif source == "open_library":
        # Add open library metadata extraction
        authors = item.get('author_name', ['Unknown'])
        metadata['authors'] = authors
        metadata['title'] = item.get('title', '')
        metadata['publisher'] = item.get('publisher', ['Unknown publisher'])[0] if item.get('publisher') else 'Unknown publisher'
        metadata['year'] = item.get('first_publish_year', '')
        metadata['isbn'] = item.get('isbn', [''])[0] if item.get('isbn') else ''
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

def format_apa_from_metadata(metadata: dict) -> str:
    """Format a reference in APA style from metadata"""
    # Format authors in APA style (Last, F. M.)
    authors = metadata.get('authors', [])
    authors_apa = []
    
    for author in authors:
        parts = author.split()
        if len(parts) > 1:
            last_name = parts[-1]
            initials = ''.join([f"{n[0]}." for n in parts[:-1]])
            authors_apa.append(f"{last_name}, {initials}")
        else:
            authors_apa.append(author)  # Just use as is if can't parse
    
    # Format author list
    if not authors_apa:
        authors_str = ""
    elif len(authors_apa) == 1:
        authors_str = authors_apa[0]
    else:
        authors_str = ", ".join(authors_apa[:-1]) + ", & " + authors_apa[-1]
    
    # Format year
    year = metadata.get('year', '')
    
    # Format title (sentence case for articles, title case for books)
    title = metadata.get('title', '')
    if title:
        # Convert to sentence case for articles
        if metadata['type'] == 'article':
            title = title[0].upper() + title[1:].lower()
        # For books, we keep the title case but ensure first letter is capitalized
        else:
            title = title[0].upper() + title[1:]
    
    if metadata['type'] == 'article':
        # Journal article formatting
        reference = f"{authors_str} ({year}). {title}. "
        
        # Journal name (italicized in final output)
        if journal := metadata.get('journal', ''):
            # Ensure journal name is in title case
            journal_words = journal.split()
            journal_title_case = ' '.join([w.capitalize() if w.lower() not in ['a', 'an', 'the', 'and', 'but', 'or', 'for', 'nor', 'on', 'at', 'to', 'from', 'by', 'in', 'of'] or i == 0 else w.lower() for i, w in enumerate(journal_words)])
            reference += f"{journal_title_case}"
        
        # Volume/issue handling
        volume = metadata.get('volume', '')
        issue = metadata.get('issue', '')
        if volume:
            reference += f", {volume}"
            if issue:
                reference += f"({issue})"
        
        # Pages handling
        if pages := metadata.get('pages', ''):
            reference += f", {pages.replace('-', '–')}"
        
        # DOI handling
        if doi := metadata.get('doi', ''):
            if not reference.endswith('.'):
                reference += '.'
            reference += f" https://doi.org/{doi}"
        else:
            if not reference.endswith('.'):
                reference += '.'
        
        return reference
    
    elif metadata['type'] == 'book':
        # Book formatting
        reference = f"{authors_str} ({year}). {title}"
        
        # Publisher
        if publisher := metadata.get('publisher', ''):
            reference += f". {publisher}"
        
        # End with period
        if not reference.endswith('.'):
            reference += '.'
        
        # ISBN (optional in APA)
        if isbn := metadata.get('isbn', ''):
            reference += f" ISBN: {isbn}"
        
        return reference
    
    return "Unknown reference format."  # Default return for unknown types

def _format_author_list(authors):
    """Helper to format author list"""
    if not authors:
        return ""
    if len(authors) > 1:
        return ", ".join(authors[:-1]) + " & " + authors[-1]
    return authors[0]

# Add these imports at the top with other imports
import re
import PyPDF2
import docx

# Add these new functions after the existing functions and before main()
def parse_citation(citation):
    """Parse citation string in multiple formats"""
    citation = citation.strip()
    # Format: 'name (year)' or '(name, year)'
    if '(' in citation and ')' in citation:
        # Handle '(name, year)' format
        if citation.startswith('('):
            content = citation.strip('()')
            if ',' in content:
                author, year_str = map(str.strip, content.split(',', 1))
                return author, int(year_str)
        # Handle 'name (year)' format
        else:
            try:
                author, rest = citation.split(' (', 1)
                year = int(rest.strip(')'))
                return author.strip(), year
            except ValueError:
                pass
    # Format: 'name, year'
    elif ',' in citation:
        try:
            author, year_str = map(str.strip, citation.split(',', 1))
            return author, int(year_str)
        except ValueError:
            pass
    
    raise ValueError("Invalid citation format")

def extract_citations_from_text(text):
    """Extract citations from text using regex patterns"""
    citation_patterns = [
        r'([A-Za-z]+)\s*\((\d{4})\)',  # Smith (2020)
        r'([A-Za-z]+)\s+and\s+([A-Za-z]+)\s*\((\d{4})\)',  # Smith and Jones (2020)
        r'([A-Za-z]+)\s+&\s+([A-Za-z]+)\s*\((\d{4})\)',  # Smith & Jones (2020)
        r'([A-Za-z]+)\s+et\s+al\.*\s*\((\d{4})\)',  # Smith et al (2020)
        r'\(([A-Za-z]+),\s*(\d{4})\)',  # (Smith, 2020)
        r'\(([A-Za-z]+)\s+and\s+([A-Za-z]+),\s*(\d{4})\)',  # (Smith and Jones, 2020)
        r'\(([A-Za-z]+)\s+&\s+([A-Za-z]+),\s*(\d{4})\)',  # (Smith & Jones, 2020)
        r'\(([A-Za-z]+)\s+et\s+al\.*,\s*(\d{4})\)'  # (Smith et al., 2020)
    ]
    
    citations = []
    for pattern in citation_patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            groups = match.groups()
            citation = {
                'text': match.group(0),
                'authors': groups[:-1],  # All groups except the last one are authors
                'year': int(groups[-1])  # Last group is always the year
            }
            citations.append(citation)
    
    return citations

def read_text_file(file_path):
    """Read content from a text file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

def read_pdf_file(file_path):
    """Read content from a PDF file"""
    text = ""
    with open(file_path, 'rb') as f:
        pdf_reader = PyPDF2.PdfReader(f)
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
    return text

def read_docx_file(file_path):
    """Read content from a DOCX file"""
    doc = docx.Document(file_path)
    return "\n".join([paragraph.text for paragraph in doc.paragraphs])

def read_file_content(file_path):
    """Read content from a file based on its extension"""
    ext = file_path.lower().split('.')[-1]
    if ext == 'txt':
        return read_text_file(file_path)
    elif ext == 'pdf':
        return read_pdf_file(file_path)
    elif ext == 'docx':
        return read_docx_file(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")

def main():
    parser = argparse.ArgumentParser(description="Find references in multiple formats")
    # Add new file argument
    parser.add_argument("--file", help="Path to file to extract citations from (txt, pdf, or docx)")
    parser.add_argument("--citation", help="Citation in format 'Author (Year)'")
    parser.add_argument("--keyword", help="Keyword to search for (optional)")
    parser.add_argument("--no-cache", action="store_true", help="Bypass cache and fetch fresh data")
    parser.add_argument("--format", choices=['text', 'json', 'csv', 'bibtex'], 
                        default='text', help="Output format (default: text)")
    parser.add_argument("--save", type=str, help="Path to save the output file (overwrites existing file)")
    parser.add_argument("--append", type=str, help="Path to append the output to existing file")
    
    args = parser.parse_args()
    
    # Handle file input if provided
    if args.file:
        try:
            content = read_file_content(args.file)
            citations = extract_citations_from_text(content)
            
            if not citations:
                print("\nNo citations found in the file.", file=sys.stderr)
                return
            
            print("\nFound citations:", file=sys.stderr)
            for i, citation in enumerate(citations, 1):
                print(f"{i}. {citation['text']}", file=sys.stderr)
            
            # Ask user which citation to search for
            while True:
                choice = input("\nEnter the number of the citation to search for (or 'q' to quit): ")
                if choice.lower() == 'q':
                    return
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(citations):
                        selected = citations[idx]
                        # Ask for optional keyword
                        keyword = input("\nEnter a keyword to refine the search (or press Enter to skip): ").strip()
                        if keyword:
                            args.keyword = keyword
                        args.citation = f"{selected['authors'][0]} ({selected['year']})"
                        break
                    else:
                        print("Invalid number. Please try again.", file=sys.stderr)
                except ValueError:
                    print("Please enter a valid number.", file=sys.stderr)
        
        except Exception as e:
            print(f"Error processing file: {str(e)}", file=sys.stderr)
            return
    
    # Require either --file or --citation
    if not args.file and not args.citation:
        parser.error("Either --file or --citation must be provided")
    
    # Continue with the existing citation processing...
    try:
        author, year = parse_citation(args.citation)
    except ValueError:
        print("Invalid citation format. Please use one of these formats:", file=sys.stderr)
        print("- Author (Year)", file=sys.stderr)
        print("- (Author, Year)", file=sys.stderr)
        print("- Author, Year", file=sys.stderr)
        return
    
    # Search both APIs
    results = []
    use_cache = not args.no_cache
    keyword = args.keyword or ""  # Use empty string if keyword is not provided
    
    print("Searching Crossref...", file=sys.stderr)
    crossref_results = search_crossref(author, year, keyword, use_cache)
    results.extend([(item, "crossref") for item in crossref_results])
    
    print("Searching Google Books...", file=sys.stderr)
    google_results = search_google_books(author, year, keyword, use_cache)
    results.extend([(item, "google_books") for item in google_results])
    
    print("Searching Semantic Scholar...", file=sys.stderr)
    semantic_results = search_semantic_scholar(author, year, keyword, use_cache)
    results.extend([(item, "semantic_scholar") for item in semantic_results])
    
    print("Searching Open Library...", file=sys.stderr)
    open_library_results = search_open_library(author, year, keyword, use_cache)
    results.extend([(item, "open_library") for item in open_library_results])
    
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
    if args.save or args.append:
        output_path = args.save or args.append
        mode = 'w' if args.save else 'a'
        
        # For append mode, add a newline separator if file exists and isn't empty
        if mode == 'a' and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            with open(output_path, mode, encoding='utf-8') as f:
                f.write('\n\n')  # Add separation between existing and new content
        
        with open(output_path, mode, encoding='utf-8') as f:
            f.write(output)
        
        action = "saved to" if args.save else "appended to"
        print(f"\nOutput {action} {output_path}", file=sys.stderr)
    else:
        print(output)

if __name__ == "__main__":
    main()