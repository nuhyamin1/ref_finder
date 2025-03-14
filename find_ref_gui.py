import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                            QTextEdit, QComboBox, QCheckBox, QFileDialog,
                            QTabWidget, QMessageBox, QGroupBox, QGridLayout,
                            QSplitter)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QTextCursor
import find_ref

class SearchWorker(QThread):
    """Worker thread to perform searches without freezing the UI"""
    finished = pyqtSignal(list)
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, author, year, keyword, use_cache):
        super().__init__()
        self.author = author
        self.year = year
        self.keyword = keyword
        self.use_cache = use_cache
        
    def run(self):
        try:
            results = []
            
            self.progress.emit("Searching Crossref...")
            crossref_results = find_ref.search_crossref(self.author, self.year, self.keyword, self.use_cache)
            results.extend([(item, "crossref") for item in crossref_results])
            
            self.progress.emit("Searching Google Books...")
            google_results = find_ref.search_google_books(self.author, self.year, self.keyword, self.use_cache)
            results.extend([(item, "google_books") for item in google_results])
            
            self.progress.emit("Searching Semantic Scholar...")
            semantic_results = find_ref.search_semantic_scholar(self.author, self.year, self.keyword, self.use_cache)
            results.extend([(item, "semantic_scholar") for item in semantic_results])
            
            self.progress.emit("Searching Open Library...")
            open_library_results = find_ref.search_open_library(self.author, self.year, self.keyword, self.use_cache)
            results.extend([(item, "open_library") for item in open_library_results])
            
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(f"Error during search: {str(e)}")


class ReferenceManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Reference Manager")
        self.setMinimumSize(800, 600)
        
        # Store search results
        self.search_results = []
        self.metadata_list = []
        
        self.init_ui()
        
    def init_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # Create a splitter for resizable sections
        splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(splitter)
        
        # Top section - Search inputs
        search_widget = QWidget()
        search_layout = QVBoxLayout(search_widget)
        
        # Title
        title_label = QLabel("Reference Manager")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        search_layout.addWidget(title_label)
        
        # Search form
        form_group = QGroupBox("Search Parameters")
        form_layout = QGridLayout()
        
        # Author and Year
        form_layout.addWidget(QLabel("Citation (Author, Year):"), 0, 0)
        self.citation_input = QLineEdit()
        self.citation_input.setPlaceholderText("e.g., 'Smith (2020)' or '(Smith, 2020)'")
        form_layout.addWidget(self.citation_input, 0, 1)
        
        # Keywords
        form_layout.addWidget(QLabel("Keywords:"), 1, 0)
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("e.g., 'machine learning' or 'climate change'")
        form_layout.addWidget(self.keyword_input, 1, 1)
        
        # Output format
        form_layout.addWidget(QLabel("Output Format:"), 2, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Text (APA)", "JSON", "CSV", "BibTeX"])
        form_layout.addWidget(self.format_combo, 2, 1)
        
        # Cache option
        self.use_cache_checkbox = QCheckBox("Use cached results (faster)")
        self.use_cache_checkbox.setChecked(True)
        form_layout.addWidget(self.use_cache_checkbox, 3, 0, 1, 2)
        
        form_group.setLayout(form_layout)
        search_layout.addWidget(form_group)
        
        # Search button
        button_layout = QHBoxLayout()
        self.search_button = QPushButton("Search References")
        self.search_button.clicked.connect(self.perform_search)
        button_layout.addWidget(self.search_button)
        
        self.save_button = QPushButton("Save Results")
        self.save_button.clicked.connect(self.save_results)
        self.save_button.setEnabled(False)
        button_layout.addWidget(self.save_button)
        
        search_layout.addLayout(button_layout)
        
        # Status area
        self.status_label = QLabel("Ready")
        search_layout.addWidget(self.status_label)
        
        # Add search section to splitter
        splitter.addWidget(search_widget)
        
        # Results section
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        
        results_label = QLabel("Results")
        results_font = QFont()
        results_font.setPointSize(14)
        results_font.setBold(True)
        results_label.setFont(results_font)
        results_layout.addWidget(results_label)
        
        # Results display
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        results_layout.addWidget(self.results_text)
        
        # Add results section to splitter
        splitter.addWidget(results_widget)
        
        # Set initial splitter sizes
        splitter.setSizes([300, 500])
        
        self.setCentralWidget(main_widget)
    
    def perform_search(self):
        # Get search parameters
        citation = self.citation_input.text().strip()
        keyword = self.keyword_input.text().strip()
        use_cache = self.use_cache_checkbox.isChecked()
        
        # Validate inputs
        if not citation or not keyword:
            QMessageBox.warning(self, "Missing Information", 
                               "Please provide both citation and keyword information.")
            return
        
        # Parse citation
        try:
            author, year = self.parse_citation(citation)
        except ValueError:
            QMessageBox.warning(self, "Invalid Citation Format", 
                               "Please use one of these formats:\n"
                               "- Author (Year)\n"
                               "- (Author, Year)\n"
                               "- Author, Year")
            return
        
        # Disable search button and update status
        self.search_button.setEnabled(False)
        self.status_label.setText("Searching...")
        self.results_text.clear()
        
        # Create and start worker thread
        self.search_worker = SearchWorker(author, year, keyword, use_cache)
        self.search_worker.progress.connect(self.update_progress)
        self.search_worker.finished.connect(self.process_results)
        self.search_worker.error.connect(self.handle_error)
        self.search_worker.start()
    
    def parse_citation(self, citation):
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
    
    def update_progress(self, message):
        self.status_label.setText(message)
    
    def handle_error(self, error_message):
        self.status_label.setText("Error occurred")
        self.search_button.setEnabled(True)
        QMessageBox.critical(self, "Search Error", error_message)
    
    def process_results(self, results):
        self.search_results = results
        
        # Extract metadata
        self.metadata_list = [find_ref.extract_metadata(item, source) for item, source in results]
        
        if not self.metadata_list:
            self.results_text.setText("No references found matching your query.\n"
                                     "Try adjusting your search terms or expanding the year range.")
            self.status_label.setText("No results found")
            self.save_button.setEnabled(False)
        else:
            # Format and display results
            self.display_formatted_results()
            self.status_label.setText(f"Found {len(self.metadata_list)} references")
            self.save_button.setEnabled(True)
        
        self.search_button.setEnabled(True)
    
    def display_formatted_results(self):
        format_type = self.format_combo.currentText()
        
        if format_type == "JSON":
            output = find_ref.format_json(self.metadata_list)
        elif format_type == "CSV":
            output = find_ref.format_csv(self.metadata_list)
        elif format_type == "BibTeX":
            output = find_ref.format_bibtex(self.metadata_list)
        else:  # Text (APA)
            apa_references = [find_ref.format_apa_from_metadata(md) for md in self.metadata_list]
            output = '\n\n'.join(apa_references)
        
        self.results_text.setText(output)
    
    def save_results(self):
        if not self.metadata_list:
            return
        
        format_type = self.format_combo.currentText()
        
        # Determine file extension
        if format_type == "JSON":
            file_filter = "JSON Files (*.json);;All Files (*)"
            default_ext = ".json"
        elif format_type == "CSV":
            file_filter = "CSV Files (*.csv);;All Files (*)"
            default_ext = ".csv"
        elif format_type == "BibTeX":
            file_filter = "BibTeX Files (*.bib);;All Files (*)"
            default_ext = ".bib"
        else:  # Text (APA)
            file_filter = "Text Files (*.txt);;All Files (*)"
            default_ext = ".txt"
        
        # Get save path
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Results", 
            os.path.expanduser("~") + "/references" + default_ext,
            file_filter
        )
        
        if not file_path:
            return  # User cancelled
        
        # Ensure file has correct extension
        if not file_path.endswith(default_ext):
            file_path += default_ext
        
        # Get formatted output
        if format_type == "JSON":
            output = find_ref.format_json(self.metadata_list)
        elif format_type == "CSV":
            output = find_ref.format_csv(self.metadata_list)
        elif format_type == "BibTeX":
            output = find_ref.format_bibtex(self.metadata_list)
        else:  # Text (APA)
            apa_references = [find_ref.format_apa_from_metadata(md) for md in self.metadata_list]
            output = '\n\n'.join(apa_references)
        
        # Save to file
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(output)
            self.status_label.setText(f"Results saved to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Error saving file: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ReferenceManagerApp()
    window.show()
    sys.exit(app.exec())