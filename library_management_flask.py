from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'your-secret-key-1234567890'  # Replace with a secure key in production

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User model for Flask-Login
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

# Mock user database (replace with real database in production)
users = {'admin': {'password': 'admin123', 'id': '1'}}

@login_manager.user_loader
def load_user(user_id):
    for username, data in users.items():
        if data['id'] == user_id:
            return User(user_id, username)
    return None

# File to store books
BOOKS_FILE = "books.json"

# Load books from file
def load_books():
    if os.path.exists(BOOKS_FILE):
        try:
            with open(BOOKS_FILE, "r") as file:
                books = json.load(file)
                for book in books:
                    if book.get("borrow_date"):
                        book["borrow_date"] = datetime.fromisoformat(book["borrow_date"])
                    if book.get("due_date"):
                        book["due_date"] = datetime.fromisoformat(book["due_date"])
                return books
        except json.JSONDecodeError:
            return []
    return []

# Save books to file
def save_books(books):
    books_copy = []
    for book in books:
        book_copy = book.copy()
        if book.get("borrow_date"):
            book_copy["borrow_date"] = book["borrow_date"].isoformat()
        if book.get("due_date"):
            book_copy["due_date"] = book["due_date"].isoformat()
        books_copy.append(book_copy)
    with open(BOOKS_FILE, "w") as file:
        json.dump(books_copy, file, indent=4)

books = load_books()

def calculate_fine(book):
    if book["available"] or not book.get("due_date"):
        return 0
    today = datetime.now()
    if today > book["due_date"]:
        days_overdue = (today - book["due_date"]).days
        return days_overdue * 1  # 1 rupee per day
    return 0

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        if username in users and users[username]['password'] == password:
            user = User(users[username]['id'], username)
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_book():
    if request.method == 'POST':
        title = request.form['title'].strip()
        author = request.form['author'].strip()
        if not title or not author:
            flash("Title and author cannot be empty!")
            return render_template('add.html')
        book = {"title": title, "author": author, "available": True, "borrower": None, "borrow_date": None, "due_date": None}
        books.append(book)
        save_books(books)
        return redirect(url_for('view_books'))
    return render_template('add.html')

@app.route('/view')
def view_books():
    return render_template('view.html', books=books, calculate_fine=calculate_fine)

@app.route('/search', methods=['GET', 'POST'])
def search_books():
    if request.method == 'POST':
        search_term = request.form['search_term'].strip().lower()
        if not search_term:
            flash("Search term cannot be empty!")
            return render_template('search.html', books=[])
        matching_books = [
            book for book in books
            if search_term in book["title"].lower() or search_term in book["author"].lower()
        ]
        return render_template('search.html', books=matching_books, calculate_fine=calculate_fine, search_term=search_term)
    return render_template('search.html', books=[])

@app.route('/borrow', methods=['GET', 'POST'])
@login_required
def borrow_book():
    if request.method == 'POST':
        name = request.form['name'].strip()
        if not name:
            flash("Name cannot be empty!")
            return render_template('borrow.html', books=[b for b in books if b["available"]])
        try:
            choice = int(request.form['book_choice']) - 1
            available_books = [b for b in books if b["available"]]
            if 0 <= choice < len(available_books):
                book_index = books.index(available_books[choice])
                books[book_index]["available"] = False
                books[book_index]["borrower"] = name
                books[book_index]["borrow_date"] = datetime.now()
                books[book_index]["due_date"] = datetime.now() + timedelta(days=14)
                save_books(books)
                return redirect(url_for('view_books'))
            else:
                flash("Invalid book number!")
                return render_template('borrow.html', books=available_books)
        except ValueError:
            flash("Please enter a valid number!")
            return render_template('borrow.html', books=available_books)
    return render_template('borrow.html', books=[b for b in books if b["available"]])

@app.route('/return', methods=['GET', 'POST'])
@login_required
def return_book():
    if request.method == 'POST':
        name = request.form['name'].strip()
        if not name:
            flash("Name cannot be empty!")
            return render_template('return.html', books=[])
        borrowed_books = [b for b in books if not b["available"] and b["borrower"] == name]
        if not borrowed_books:
            flash(f"No books borrowed by {name}.")
            return render_template('return.html', books=[])
        if 'book_choice' in request.form:
            try:
                choice = int(request.form['book_choice']) - 1
                if 0 <= choice < len(borrowed_books):
                    book_index = books.index(borrowed_books[choice])
                    fine = calculate_fine(books[book_index])
                    books[book_index]["available"] = True
                    books[book_index]["borrower"] = None
                    books[book_index]["borrow_date"] = None
                    books[book_index]["due_date"] = None
                    save_books(books)
                    message = f"You returned '{books[book_index]['title']}'"
                    if fine > 0:
                        message += f". Please pay a fine of ₹{fine}."
                    return render_template('return.html', message=message, books=[])
                else:
                    flash("Invalid book number!")
                    return render_template('return.html', books=borrowed_books, calculate_fine=calculate_fine)
            except ValueError:
                flash("Please enter a valid number!")
                return render_template('return.html', books=borrowed_books, calculate_fine=calculate_fine)
        return render_template('return.html', books=borrowed_books, calculate_fine=calculate_fine)
    return render_template('return.html', books=[])

if __name__ == '__main__':
    app.run(debug=True)