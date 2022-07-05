import os
from datetime import datetime
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

### datetime object containing date and time ###
now = datetime.now()

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show portfolio of stocks"""
    id = session.get("user_id")
    symbols = db.execute("SELECT symbol FROM portifolios WHERE user_id = ?", id)
    cash = db.execute("SELECT cash FROM users WHERE id = ?", id)[0]["cash"]
    stocks = []
    total_value = 0
    for symbol in symbols:
        ### convert a key value pair into just a variable that has the symbol ###
        symbol = symbol["symbol"]
        shares = db.execute("SELECT shares FROM portifolios WHERE user_id = ? AND symbol = ?", id, symbol)[0]["shares"]
        stock = lookup(symbol)
        price = stock["price"]
        name = stock["name"]
        total_stock = shares * price
        total_value += total_stock
        stocks.append({"name": name, "symbol": symbol, "shares": shares, "price": usd(price), "total": usd(total_stock)})
    total_money = total_value + cash
    alert = "None"
    if request.method == "POST":
        alert = request.args.get("alert")
    return render_template("index.html", stocks=stocks, cash=usd(cash), total=usd(total_money), alert=alert)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        # ensures symbol exists and is a real company
        if not symbol:
            return apology("Symbol can't be empty")
        stock = lookup(symbol)
        if not stock:
            return apology("Symbol Doesn't exist")
        price = stock["price"]
        name = stock["name"]
        symbol = stock["symbol"]
        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("Shares must be an integer")
        if shares <= 0:
            return apology("Shares must be a positive integer")
        id = session.get("user_id")
        available_cash = db.execute("SELECT cash FROM users WHERE id = ?", id)[0]["cash"]
        shares_price = shares * price
        if shares_price > available_cash:
            return apology("Not enough cash")
        available_cash -= shares_price
        ### update users cash and record the purchase in transactions ###
        DateAndTime = now.strftime("%d/%m/%Y %H:%M:%S")
        db.execute("INSERT INTO transactions(user_id,type,name,symbol,price,shares,date) VALUES(?,?,?,?,?,?,?)",
                   id, "BUY", name, symbol, price, shares, DateAndTime)
        update_portifolios("BUY", symbol, shares)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", available_cash, id)
        return redirect(url_for("index", alert="Bought!"), code=307)
    if request.method == "GET":
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    id = session.get("user_id")
    transactions = db.execute("SELECT type,name,symbol,price,shares,date FROM transactions WHERE user_id = ?", id)

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stocks quote."""
    stocks = []
    id = session.get("user_id")
    if request.method == "POST":
        new_symbol = request.form.get("symbol").upper()
        if new_symbol:
            try:
                db.execute("INSERT INTO watchlist(user_id,symbols) VALUES(?,?)", id, new_symbol)
            except ValueError:
                return apology("Symbol already Exists!")
        else:
            return apology("Symbol can't be empty.")
    symbols = db.execute("SELECT symbols FROM watchlist WHERE user_id = ?", id)
    for symbol in symbols:
        stock = lookup(symbol["symbols"])
        if not stock:
            return apology("Symbol Doesn't Exist!")
        stock["price"] = usd(stock["price"])
        stocks.append(stock)

    return render_template("quote.html", stocks=stocks)


@app.route("/delete", methods=["POST", "GET"])
@login_required
def delete():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if symbol:
            db.execute("DELETE FROM watchlist WHERE symbols = ?", symbol)
        return redirect("/quote")
    return redirect("/quote")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # get variables from the request
        new_username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        # ensure right usage
        if not new_username:
            return apology("Username can't be empty.", 400)
        users = db.execute("SELECT username FROM users")
        for user in users:
            if new_username == user["username"]:
                return apology("Username already exists.", 400)
        if not password:
            return apology("Password can't be empty", 400)
        if password != confirmation:
            return apology("Passwords don't match.", 400)
        hash = generate_password_hash(password)
        try:
            db.execute("INSERT INTO users(username,hash) VALUES(?,?)", new_username, hash)
        except ValueError:
            apology("User name Taken")
        return render_template("login.html")

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    id = session.get("user_id")
    symbols = db.execute("SELECT DISTINCT symbol FROM transactions WHERE user_id=?", id)
    available_cash = db.execute("SELECT cash FROM users WHERE id = ?", id)[0]["cash"]
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        try:
            shares = db.execute("SELECT shares FROM portifolios WHERE user_id = ? AND symbol = ?", id, symbol)
        except:
            return apology("you don't have shares of this stock")
        shares = shares[0]["shares"]
        shares_to_sell = int(request.form.get("shares"))
        if shares <= 0:
            return apology("Shares must be a positive int!")
        if shares < shares_to_sell:
            return apology("Not enough Shares!")
        stock = lookup(symbol)
        price = stock["price"]
        name = stock["name"]
        price_all = price * shares_to_sell
        ## Commit changes ###
        available_cash += price_all
        db.execute("UPDATE users SET cash = ? WHERE id = ?", available_cash, id)
        DateAndTime = now.strftime("%d/%m/%Y %H:%M:%S")
        db.execute("INSERT INTO transactions(user_id,type,name,symbol,price,shares,date) VALUES(?,?,?,?,?,?,?)",
                   id, "SELL", name, symbol, price, shares_to_sell, DateAndTime)
        update_portifolios("SELL", symbol, shares_to_sell)
        return redirect(url_for("index", alert="Sold!"), code=307)
    symbol = None
    if request.method == "GET" and request.args.get("symbol"):
        symbol = request.args.get("symbol")
    return render_template("sell.html", symbols=symbols, requested_symbol=symbol)


def update_portifolios(type, symbol, new_shares):
    """updates the portifolio of the user"""
    id = session.get("user_id")
    existing_shares = db.execute("SELECT shares FROM portifolios WHERE user_id = ? AND symbol = ?", id, symbol)
    if existing_shares:
        existing_shares = existing_shares[0]["shares"]
        if type == "BUY":
            shares = existing_shares + new_shares
        elif type == "SELL":
            shares = existing_shares - new_shares
    else:
        shares = new_shares
    db.execute("REPLACE INTO portifolios(user_id,symbol,shares) VALUES(?,?,?)", id, symbol, shares)
