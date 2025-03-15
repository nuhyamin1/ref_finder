import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                            QTextEdit, QComboBox, QCheckBox, QFileDialog,
                            QTabWidget, QMessageBox, QGroupBox, QGridLayout,
                            QSplitter, QListWidget)
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


# Add after the existing imports
from PyQt6.QtWidgets import QFileDialog, QListWidget, QDialog, QVBoxLayout, QPushButton, QLabel

# Add this new dialog class before the ReferenceManagerApp class
class CitationSelectionDialog(QDialog):
    def __init__(self, citations, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Citation")
        self.setModal(True)
        layout = QVBoxLayout(self)
        
        # Instructions
        layout.addWidget(QLabel("Select a citation to search for:"))
        
        # List of citations
        self.citation_list = QListWidget()
        for citation in citations:
            self.citation_list.addItem(citation['text'])
        layout.addWidget(self.citation_list)
        
        # Keyword input
        layout.addWidget(QLabel("Enter keyword to refine search (optional):"))
        self.keyword_input = QLineEdit()
        layout.addWidget(self.keyword_input)
        
        # Buttons
        button_box = QHBoxLayout()
        self.select_button = QPushButton("Search")
        self.select_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_box.addWidget(self.select_button)
        button_box.addWidget(self.cancel_button)
        layout.addLayout(button_box)
        
        self.citation_list.itemSelectionChanged.connect(self.enable_select)
        self.select_button.setEnabled(False)
    
    def enable_select(self):
        self.select_button.setEnabled(bool(self.citation_list.selectedItems()))
    
    def get_selection(self):
        if self.citation_list.currentItem():
            return {
                'index': self.citation_list.currentRow(),
                'keyword': self.keyword_input.text().strip()
            }
        return None


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
        
        # File input
        form_layout.addWidget(QLabel("File (optional):"), 0, 0)
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Select a file to extract citations from")
        file_button_layout = QHBoxLayout()
        file_button_layout.addWidget(self.file_input)
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_file)
        file_button_layout.addWidget(self.browse_button)
        form_layout.addLayout(file_button_layout, 0, 1)
        
        # Author and Year (adjust row numbers)
        form_layout.addWidget(QLabel("Citation (Author, Year):"), 1, 0)
        self.citation_input = QLineEdit()
        self.citation_input.setPlaceholderText("e.g., 'Smith (2020)' or '(Smith, 2020)'")
        form_layout.addWidget(self.citation_input, 1, 1)
        
        # Keywords (make it optional)
        form_layout.addWidget(QLabel("Keywords (optional):"), 1, 0)
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("e.g., 'machine learning' (optional)")
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
        
        self.append_button = QPushButton("Append Results")
        self.append_button.clicked.connect(lambda: self.save_results(append=True))
        self.append_button.setEnabled(False)
        button_layout.addWidget(self.append_button)
        
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
        
        # Create tab widget for different views
        self.results_tabs = QTabWidget()
        
        # Text Edit tab
        text_tab = QWidget()
        text_layout = QVBoxLayout(text_tab)
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(False)
        text_layout.addWidget(self.results_text)
        edit_note = QLabel("Note: You can edit the results before saving")
        edit_note.setStyleSheet("color: gray; font-style: italic;")
        text_layout.addWidget(edit_note)
        self.results_tabs.addTab(text_tab, "Text View")
        
        # List Widget tab
        list_tab = QWidget()
        list_layout = QVBoxLayout(list_tab)
        self.results_list = QListWidget()
        self.results_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        list_layout.addWidget(self.results_list)
        list_note = QLabel("Note: Click an item to select it for saving")
        list_note.setStyleSheet("color: gray; font-style: italic;")
        list_layout.addWidget(list_note)
        self.results_tabs.addTab(list_tab, "List View")
        
        results_layout.addWidget(self.results_tabs)
        
        # Add results section to splitter
        splitter.addWidget(results_widget)
        
        # Set initial splitter sizes
        splitter.setSizes([300, 500])
        
        self.setCentralWidget(main_widget)
    
    def perform_search(self):
        # Check if we're searching by file
        if self.file_input.text().strip():
            try:
                content = find_ref.read_file_content(self.file_input.text().strip())
                citations = find_ref.extract_citations_from_text(content)
                
                if not citations:
                    QMessageBox.warning(self, "No Citations Found", 
                                      "No citations were found in the selected file.")
                    return
                
                # Show citation selection dialog
                dialog = CitationSelectionDialog(citations, self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    selection = dialog.get_selection()
                    if selection:
                        selected_citation = citations[selection['index']]
                        self.citation_input.setText(f"{selected_citation['authors'][0]} ({selected_citation['year']})")
                        if selection['keyword']:
                            self.keyword_input.setText(selection['keyword'])
                
                # Continue with normal search if citation was selected
                if not self.citation_input.text().strip():
                    return
                    
            except Exception as e:
                QMessageBox.critical(self, "File Error", f"Error processing file: {str(e)}")
                return
        
        # Get search parameters
        citation = self.citation_input.text().strip()
        keyword = self.keyword_input.text().strip()
        use_cache = self.use_cache_checkbox.isChecked()
        
        # Validate inputs (only citation is required now)
        if not citation:
            QMessageBox.warning(self, "Missing Information", 
                               "Please provide citation information.")
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
            self.append_button.setEnabled(False)
        else:
            self.display_formatted_results()
            self.status_label.setText(f"Found {len(self.metadata_list)} references")
            self.save_button.setEnabled(True)
            self.append_button.setEnabled(True)
        
        self.search_button.setEnabled(True)
    
    def display_formatted_results(self):
        format_type = self.format_combo.currentText()
        
        # Clear previous results
        self.results_text.clear()
        self.results_list.clear()
        
        if format_type == "JSON":
            output = find_ref.format_json(self.metadata_list)
        elif format_type == "CSV":
            output = find_ref.format_csv(self.metadata_list)
        elif format_type == "BibTeX":
            output = find_ref.format_bibtex(self.metadata_list)
        else:  # Text (APA)
            apa_references = [find_ref.format_apa_from_metadata(md) for md in self.metadata_list]
            output = '\n\n'.join(apa_references)
            # Add items to list widget
            for ref in apa_references:
                self.results_list.addItem(ref)
        
        self.results_text.setText(output)

    def save_results(self, append=False):
        if not self.metadata_list:
            return
        
        # Get the output based on current view and selection
        if self.results_tabs.currentIndex() == 1:  # List View
            current_item = self.results_list.currentItem()
            if not current_item:
                QMessageBox.warning(self, "No Selection", 
                                   "Please select an item from the list to save.")
                return
            output = current_item.text()
        else:  # Text View
            output = self.results_text.toPlainText()
        
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
        
        # Save to file
        try:
            # Read existing content first if appending
            existing_content = ""
            if append and os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        existing_content = f.read()
                except Exception as e:
                    QMessageBox.warning(self, "File Access Warning", 
                                      f"Could not read existing file: {str(e)}\nCreating new file instead.")
                    append = False
            
            # Write content
            with open(file_path, 'w', encoding='utf-8') as f:
                if append and existing_content:
                    f.write(existing_content)
                    if not existing_content.endswith('\n\n'):
                        f.write('\n\n')
                f.write(output)
            
            action = "appended to" if append else "saved to"
            self.status_label.setText(f"Results {action} {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Error saving file: {str(e)}")

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select File",
            os.path.expanduser("~"),
            "Documents (*.txt *.pdf *.docx);;All Files (*)"
        )
        if file_path:
            self.file_input.setText(file_path)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ReferenceManagerApp()
    window.show()
    sys.exit(app.exec())