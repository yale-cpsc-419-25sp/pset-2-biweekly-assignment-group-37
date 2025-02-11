import sys
import socket
import json
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QListWidget, QLabel, QMessageBox
)
from PySide6.QtGui import QFont

# Use a fixed-width font (Monaco or fallback)
fixed_font = QFont("Monaco")
fixed_font.setStyleHint(QFont.StyleHint.TypeWriter)
fixed_font.setFixedPitch(True)

class MainWindow(QWidget):
    def __init__(self, host, port):
        super().__init__()
        self.host = host
        self.port = port
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("YUAG Client")
        # Set the window to be no larger than half the screen width/height.
        screen = QApplication.primaryScreen().availableGeometry()
        self.setFixedSize(screen.width() // 2, screen.height() // 2)

        main_layout = QVBoxLayout()

        # Create a horizontal layout for the search fields
        form_layout = QHBoxLayout()
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Label")
        self.classifier_edit = QLineEdit()
        self.classifier_edit.setPlaceholderText("Classifier")
        self.agent_edit = QLineEdit()
        self.agent_edit.setPlaceholderText("Agent")
        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("Date")

        for widget in [self.label_edit, self.classifier_edit, self.agent_edit, self.date_edit]:
            widget.setFont(fixed_font)

        form_layout.addWidget(QLabel("Label:"))
        form_layout.addWidget(self.label_edit)
        form_layout.addWidget(QLabel("Classifier:"))
        form_layout.addWidget(self.classifier_edit)
        form_layout.addWidget(QLabel("Agent:"))
        form_layout.addWidget(self.agent_edit)
        form_layout.addWidget(QLabel("Date:"))
        form_layout.addWidget(self.date_edit)
        main_layout.addLayout(form_layout)

        # Submit button
        self.submit_button = QPushButton("Submit")
        main_layout.addWidget(self.submit_button)

        # Results list (formatted as a table)
        self.results_list = QListWidget()
        self.results_list.setFont(fixed_font)
        main_layout.addWidget(self.results_list)

        self.setLayout(main_layout)

        # Connect signals
        self.submit_button.clicked.connect(self.submit_query)
        for edit in [self.label_edit, self.classifier_edit, self.agent_edit, self.date_edit]:
            edit.returnPressed.connect(self.submit_query)

        # Double-clicking a result shows details (for simplicity, we use a message box)
        self.results_list.itemDoubleClicked.connect(self.show_details)

    def submit_query(self):
        # Collect filter criteria from the fields
        filters = {
            "label": self.label_edit.text().strip(),
            "classifier": self.classifier_edit.text().strip(),
            "agent": self.agent_edit.text().strip(),
            "date": self.date_edit.text().strip()
        }
        request_json = json.dumps(filters)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.host, self.port))
            s.sendall(request_json.encode("utf-8"))
            # Read until EOF
            response_chunks = []
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                response_chunks.append(chunk)
            s.close()
            response_json = b"".join(response_chunks).decode("utf-8")
            response = json.loads(response_json)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error connecting to server: {e}")
            return

        # Clear previous results and populate new ones.
        self.results_list.clear()
        if "error" in response:
            QMessageBox.critical(self, "Server Error", response["error"])
            return

        results = response.get("results", [])
        # Sort results by label (ascending)
        results.sort(key=lambda r: r.get("label", "").lower())

        # Format header row and add as first two items.
        header = f"{'Label'.ljust(30)}{'Date'.ljust(15)}{'Produced By'.ljust(40)}{'Classified As'.ljust(30)}"
        self.results_list.addItem(header)
        self.results_list.addItem("-" * len(header))
        for res in results:
            # For each result, extract fields.
            label = (res.get("label") or "")[:30].ljust(30)
            date = (res.get("date") or "")[:15].ljust(15)
            produced_by = (res.get("produced_by") or "")[:40].ljust(40)
            classified_as = (res.get("classified_as") or "")[:30].ljust(30)
            line = f"{label}{date}{produced_by}{classified_as}"
            self.results_list.addItem(line)

    def show_details(self, item):
        # In a complete solution, you would extract the object ID and show a detail dialog.
        # For simplicity, here we just show the text of the selected row.
        QMessageBox.information(self, "Detail", item.text())

def main():
    if len(sys.argv) != 3:
        print("Usage: python lux.py host port")
        sys.exit(1)
    host = sys.argv[1]
    try:
        port = int(sys.argv[2])
    except ValueError:
        print("Port must be an integer")
        sys.exit(1)
    app = QApplication(sys.argv)
    window = MainWindow(host, port)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
