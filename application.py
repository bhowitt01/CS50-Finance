import os

## export API_KEY=pk_4944165eaead46f8ab899e27ca4a697e ##

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

import datetime

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    rows = db.execute("SELECT symbol, price, SUM(shares) AS shares FROM purchases JOIN users ON id == user_id WHERE user_id == ? GROUP BY symbol HAVING SUM(shares) > 0", session["user_id"])
    if not rows:
        return apology("No previous purchases.", 200)
    bal = db.execute("SELECT cash FROM users WHERE id == ?", session["user_id"])
    for row in rows:
        quoted = lookup(row["symbol"])
        total = float(quoted["price"]) * float(row["shares"])
        projectedVal = float(bal[0]["cash"]) + float(total)
    return render_template("index.html", rows = rows, cash = round(bal[0]["cash"],2), total_value = round(projectedVal, 2))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        sold = False
        symbol = request.form.get("symbol").upper()
        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("invalid shares", 400)
        if shares < 0:
            return apology("invalid shares", 400)
        quoted = lookup(symbol)
        if not quoted:
            return apology("invalid symbol",400)
            return apology("must buy a minimum of one share",400)
        userBalance = db.execute("SELECT cash FROM users WHERE id == ?", session["user_id"])
        cash = float(userBalance[0]["cash"])
        num = float(quoted["price"])
        price = float(quoted["price"]) * float(shares)
        if cash < price:
            return apology("insufficient balance",400)
        userBalance = cash - price
        date_time = datetime.datetime.now()
        date_time = date_time.strftime("%Y-%m-%d %H:%M:%S")
        db.execute("UPDATE users SET cash = ? WHERE id = ?", userBalance, session["user_id"])
        db.execute("INSERT INTO purchases (user_id, symbol, price, time, shares, sold) VALUES(?,?,?,?,?,?)", session["user_id"], quoted["symbol"], num, date_time, shares, sold)
        return render_template("bought.html", shares=shares, name=quoted["name"], symbol=quoted["symbol"], price=price)
    else:
        return render_template("buy.html")
    return apology("not working",500)


@app.route("/history")
@login_required
def history():
    rows = db.execute("SELECT symbol, price, shares, time, sold FROM purchases WHERE user_id == ?", session["user_id"])
    sold = list()
    return render_template("history.html", rows = rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

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
    if request.method == "POST":
        symbol = request.form.get("symbol")
        quoted = lookup(symbol)
        if not quoted:
            return apology("invalid symbol", 400)
        return render_template("quoted.html",name=quoted["name"], symbol=quoted["symbol"], price='${:,.2f}'.format(quoted["price"]))
    else:
        return render_template("quote.html")

    return apology("not working", 500)


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        if not request.form.get("username"):
            return apology("you must enter a username", 400)
        elif not request.form.get("password"):
            return apology("you must enter a password", 400)

        username = request.form.get("username")
        passHash = generate_password_hash(request.form.get("password"))
        userCheck = db.execute("SELECT username FROM users WHERE username == ?", username)

        if len(username) == 0:
            return apology("you must enter a username", 400)

        if len(userCheck) != 0:
            return apology("this username is already taken", 400)

        if check_password_hash(passHash, request.form.get("confirmation")):
            db.execute("INSERT INTO users (username, hash) VALUES(?,?)", username, passHash)
            return redirect("/")
        else:
            return apology("passwords do not match", 400)
    else:
        return render_template("register.html")

    return apology("invalid username/password", 400)


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    options = db.execute("SELECT symbol FROM purchases WHERE user_id == ? GROUP BY symbol HAVING SUM(shares) > 0", session["user_id"])

    if request.method == "POST":
        sold = True
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        try:
            shares = int(shares)
        except:
            return apology("invalid shares", 400)
        if not symbol:
            return apology("symbol not given", 400)
        if not shares:
            return apology("shares not given", 400)
        checkShares = db.execute("SELECT SUM(shares) AS shares FROM purchases WHERE user_id == ? AND symbol == ?", session["user_id"], symbol)
        checkBal = db.execute("SELECT cash FROM users WHERE id == ?", session["user_id"])
        cS = checkShares[0]["shares"]
        cV = lookup(symbol)
        if shares > int(cS):
            return apology("shares provided are greater than shares owned", 400)
        if shares < 0:
            return apology("shares must be a positive integer", 400)
        if not lookup(symbol):
            return apology("invalid symbol", 400)
        newShare = int(cS) - int(shares)
        fltBal = float(checkBal[0] ["cash"])
        fltcV = float(cV["price"]) * float(shares)
        newBal = fltBal + fltcV
        shares = 0 - int(shares)
        date_time = datetime.datetime.now()
        date_time = date_time.strftime("%Y-%m-%d %H:%M:%S")
        db.execute("INSERT INTO purchases (user_id, symbol, price, time, shares, sold) VALUES(?,?,?,?,?,?)", session["user_id"], symbol, cV["price"], date_time, shares, sold)
        db.execute("UPDATE users SET cash = ? WHERE id == ?", newBal, session["user_id"])
        shares = 0 - int(shares)
        return render_template("sold.html", shares=shares, symbol=symbol, fltcV=fltcV)
    else:
        return render_template("sell.html", options=options)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)