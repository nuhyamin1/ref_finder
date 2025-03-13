# Ref Finder

Ref Finder is a command-line tool that helps researchers and students quickly find academic references in APA format. It searches multiple academic databases and formats the results according to APA style guidelines.

## Features

- Search for references by author, year, and keyword
- Automatically format results in APA style
- Search both Crossref and Google Books APIs
- Handle multiple authors, journal titles, and publication details
- Proper formatting of volume/issue numbers and page ranges

## Installation

1. Clone this repository:
```bash
git clone https://github.com/[your-username]/ref-finder.git
cd ref-finder
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Basic usage:
```bash
python find_ref.py --citation "Author (Year)" --keyword "Topic"
```

Example:
```bash
python find_ref.py --citation "Chomsky (1965)" --keyword "Syntax"
```

## API Requirements

This tool uses the following APIs:
- Crossref API (no API key required)
- Google Books API (no API key required)

## Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a new branch (`git checkout -b feature/YourFeatureName`)
3. Commit your changes (`git commit -m 'Add some feature'`)
4. Push to the branch (`git push origin feature/YourFeatureName`)
5. Open a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Crossref for their excellent API
- Google Books API team
- APA Style for their formatting guidelines
