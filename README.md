# 🎓 Academic Scholar Finder

A fast and elegant desktop application for searching and filtering academic scholar data from a CSV file, built with **PySide6** and **pandas**.

## ✨ Features

- **Advanced Filtering**
  - By country, university, research interests
  - Numeric filters: citation count (`citedby`), World Rank, Country Ranking

- **Interactive Table View**
  - Quick pagination (20 records per page – adjustable)
  - Sort data by clicking on any column header

- **Export Results**
  - Save filtered results as a CSV file

- **Beautiful & Professional UI**
  - Smooth and responsive interface powered by Qt and pandas

## 📋 Prerequisites

- Python 3.10 or higher

## 🚀 Installation & Run

1. Clone or download the project
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```

## 📊 Data Format

- Replace the `data.csv` file with your own dataset
- Column names must match the following structure:

| Column Name       | Description                                          |
| ----------------- | ---------------------------------------------------- |
| `scholar_id`      | Unique scholar identifier                            |
| `url_picture`     | Profile picture URL                                  |
| `name`            | Full name of the scholar                             |
| `affiliation`     | University/institution affiliation                   |
| `email_domain`    | Email domain                                         |
| `interests`       | List of interests (e.g., `['Physics','AI']`)         |
| `citedby`         | Total citation count                                 |
| `Country Ranking` | Rank within the country                              |
| `World Rank`      | Global rank                                          |
| `Country`         | Country name                                         |
| `Institution`     | Institution name                                     |

> ⚠️ **Important:** The `interests` column should contain a Python list-like string (e.g., `"['Physics','AI']"`).

## 🪟 Building Windows Executable (Optional)

To create a standalone `.exe` file:

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name ScholarFinder main.py
```

The executable will be located in the `dist/` folder.

## 📁 Project Structure

```
Academic-Scholar-Finder/
├── main.py              # Main application entry point
├── requirements.txt     # Python dependencies
├── data.csv             # Dataset (replace with your own)
└── README.md            # This file
```

## 🛠️ Technologies Used

- **PySide6** – Qt-based GUI framework
- **pandas** – Data manipulation and filtering
- **Python 3.10+**

## 📄 License

This project is open-source and available under the MIT License.

## 🤝 Contributing

Feel free to open issues or submit pull requests for improvements.

---

🎉 Happy searching!
```

To save this file:

1. **Copy** the entire content above
2. **Create** a new file named `README.md` in your project folder
3. **Paste** the content into the file
4. **Save** it

Or if you're using a terminal:

```bash
nano README.md
# or
vim README.md
# or on Windows:
notepad README.md
```
