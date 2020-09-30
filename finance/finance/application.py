import os
import datetime
import requests
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, getValueNow, passwordValidator

# Configure application
app = Flask(__name__)

import logging

log = logging.getLogger('werkzeug')
log.disabled = True
app.logger.disabled = True


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

fun = getValueNow

@app.route("/")
@login_required
def index():
    currentUser = session.get("user_id")
    currentUserPurchases = db.execute("SELECT * FROM purchases WHERE id=? GROUP BY stock", currentUser)

    if len(currentUserPurchases) == 0:
        return render_template("noactivityyet.html")

    for v in currentUserPurchases:
        v['updated_ammount'] = round(v['updated_ammount'], 2)
        v['current_value'] = round(v['current_value'] , 2)

    cash = db.execute("SELECT updated_ammount FROM purchases WHERE id=? ORDER BY date DESC LIMIT 1", currentUser)#  < -----
    grandTotal = 0
    totalHoldingValues = db.execute("SELECT value_of_holding FROM purchases WHERE id=? GROUP BY stock ", currentUser)
    vals = []

    if len(totalHoldingValues) == 0:
        grandTotal = cash
    else:
        for w in totalHoldingValues:
            vals.append(w['value_of_holding'])
            finalVal = sum(vals)

    grandTotal = finalVal + cash[0]['updated_ammount']
    grandTotal = round(grandTotal, 2)
    arrayFreeFromZeros = []

    for y in currentUserPurchases:
        if y['qty_currently_owned'] != 0:
            arrayFreeFromZeros.append(y)
    return render_template("index.html", stock=arrayFreeFromZeros, cash=round(cash[0]['updated_ammount'], 2), fun=fun, grandTotal=grandTotal)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = request.form.get("symbol")
        symbol = symbol.upper() # <- ++
        shares = request.form.get("shares")

        #ESTAO AMBOS OS CAMPOS VAZIOS
        if not shares and not symbol:
            flash('Please provide information about stock and shares.')
            return render_template('buy.html')

        if len(symbol) == 0:
            flash('Empty stock!')
            return render_template('buy.html')

        if not shares:
            flash('Please provide share!')
            return render_template('buy.html')

        shares = int(shares)

        result = lookup(symbol)
        if result == None:
            flash('Wrong stock!')
            return render_template('buy.html')
        elif shares < 0:
            flash('Please provide positive number.')
            return render_template('buy.html')

        #OK:
        else:
            currentStockPrice = result['price']
            currentUser = session.get("user_id")
            logged = db.execute("SELECT * FROM users WHERE id=?", currentUser)
            availableAmount = logged[0]['cash']

            if currentStockPrice > availableAmount:
                flash('Not enough money to complete this purchase.')
                return render_template('buy.html')
            else:
                val = availableAmount - currentStockPrice
                checkIfItIsFirstPurchaseFromId = db.execute("SELECT id FROM purchases WHERE id=?", logged[0]['id'])
                #user didn't buy nothing yet:
                if len(checkIfItIsFirstPurchaseFromId) == 0:
                    if shares == 1 and currentStockPrice <= availableAmount:
                        db.execute("INSERT INTO purchases (id, date,stock,current_value,stock_value,updated_ammount, qty_of_shares, type_of_transaction, qty_currently_owned, value_of_holding) VALUES(:id, :date,:stock,:current_value,:stock_value,:updated_ammount, :qty_of_shares, :type_of_transaction, :qty_currently_owned, :value_of_holding)", id=logged[0]['id'], date=datetime.datetime.now(), stock=symbol, current_value=round(availableAmount,2), stock_value=currentStockPrice, updated_ammount=round(val,2), qty_of_shares=shares, type_of_transaction="Purchase", qty_currently_owned=shares, value_of_holding=round(currentStockPrice*shares, 2))

                    elif shares > 1:
                        valorApagar = shares * currentStockPrice
                        db.execute("INSERT INTO purchases (id, date,stock,current_value,stock_value,updated_ammount, qty_of_shares, type_of_transaction, qty_currently_owned, value_of_holding) VALUES(:id, :date,:stock,:current_value,:stock_value,:updated_ammount, :qty_of_shares, :type_of_transaction, :qty_currently_owned, :value_of_holding)", id=logged[0]['id'], date=datetime.datetime.now(), stock=symbol, current_value=10000, stock_value=currentStockPrice, updated_ammount=10000-valorApagar, qty_of_shares=shares, type_of_transaction="purchase", qty_currently_owned=shares, value_of_holding=round(currentStockPrice*shares, 2))
                else:
                    logadoAgora =  session.get("user_id")
                    mostRecent = db.execute(f"SELECT updated_ammount FROM purchases WHERE purchases.id={logadoAgora} ORDER BY date DESC LIMIT 1")
                    valorApagar = shares * currentStockPrice
                    counterOfStocksCurrentlyOwned = db.execute("SELECT qty_currently_owned FROM purchases WHERE purchases.id=? AND purchases.stock=?", logadoAgora, symbol) # o erro era por ter request. form('stock') e nao uma var como está agora
                    qtyCount = 0
                    sumValues = []

                    if len(counterOfStocksCurrentlyOwned) == 0:
                        qtyCount = shares # qd n tenho ainda nenhuma compra deste stock, o shares é = a a qtdd c q vou ficar

                    if len(counterOfStocksCurrentlyOwned) != 0:
                        for v in counterOfStocksCurrentlyOwned:
                            sumValues.append(v['qty_currently_owned'])
                            current = sumValues[-1]
                            qtyCount = current + shares

                    if mostRecent[0]['updated_ammount'] >= valorApagar:
                        db.execute("INSERT INTO purchases (id, date,stock,current_value,stock_value,updated_ammount, qty_of_shares, type_of_transaction, qty_currently_owned, value_of_holding) VALUES(:id, :date,:stock,:current_value,:stock_value,:updated_ammount, :qty_of_shares, :type_of_transaction, :qty_currently_owned, :value_of_holding)", id=logged[0]['id'], date=datetime.datetime.now(), stock=symbol, current_value=round(mostRecent[0]['updated_ammount'], 2), stock_value=currentStockPrice, updated_ammount=round(mostRecent[0]['updated_ammount']-(shares *currentStockPrice), 2), qty_of_shares=shares, type_of_transaction="Purchase", qty_currently_owned=qtyCount,  value_of_holding=round(currentStockPrice*qtyCount,2)) #qtyCount em x de shares
                    else:
                        flash('Out of money to complete this purchase!')
                        return render_template('buy.html')

    flash('You completed your purchase successfully.')
    return render_template('buy.html')

@app.route("/history")
@login_required
def history():
    currentUser = session.get("user_id")
    currentUserPurchases = db.execute("SELECT * FROM purchases WHERE id=?", currentUser)
    if len(currentUserPurchases) == 0:
        return render_template("noactivityyet.html")
    for v in currentUserPurchases:
        v['updated_ammount'] = round(v['updated_ammount'], 2)
        v['current_value'] = round(v['current_value'] , 2)
    return render_template("history.html", stock=currentUserPurchases)


@app.route("/login", methods=["GET", "POST"])
def login():
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        if not request.form.get("username"):
            flash('Please provide username')
            return render_template('login.html')

        elif not request.form.get("password"):
            flash('Please provide password')
            return render_template('login.html')

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flash('Invalid username and/or password')
            return render_template('login.html')

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        u = request.form.get("username")
        flash(f'Welcome, {u}')
        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    # Forget any user_id
    session.clear()
    flash('You have been logged out! See you soon.')
    return render_template('login.html')


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    #if it is a get req, show me the form to submit the info
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")
        result = lookup(symbol)
        return render_template("quoted.html", name=result["name"], price=result["price"], symbol=result["symbol"])


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirm")
        existent = db.execute("SELECT username FROM users")
        repeated = False

        for i in existent:
            if i['username'] == username:
                repeated = True

        if username and not password:
            flash('Please provide password.')
            return render_template('register.html')
        elif not username and password:
            flash('Please provide username.')
            return render_template('register.html')
        elif not username and not password:
            flash('Please provide username and password.')
            return render_template('register.html')
        elif password != confirmation:
            flash("Password and confirm password don't match.")
            return render_template('register.html')
        elif repeated:
            flash("Username already taken, sorry!")
            return render_template('register.html')
        else:
            if passwordValidator(password):
                #fazer hash da pass:
                passwordHash = generate_password_hash(password)
                db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=username, hash=passwordHash)
                flash("You have registered successfully!")
                return render_template('login.html')
            else:
                flash("Password must have a 10 chars length, 2 digits, 2 letters, and one of the following:  '!' '?' '#' '$' '%' '&' ") # aqui vai ser preciso limpar os forms
                return render_template('register.html')


@app.route("/changepassword", methods=["GET", "POST"])
@login_required
def changepassword():
    user_id =  session.get("user_id")
    if request.method == "GET":
        return render_template("changepassword.html")
    else:
        oldpassword = request.form.get("oldpassword")
        newpassword = request.form.get("newpassword")
        repeatpassword = request.form.get("repeatpassword")

        if not oldpassword or not newpassword or not repeatpassword:
            flash('You must fill all required fields.')
            return render_template('changepassword.html')

        #validate if provided old pass is correct
        else:
            user = db.execute("SELECT * FROM users WHERE id=?", user_id)
            if len(user) != 1 or not check_password_hash(user[0]["hash"], request.form.get("oldpassword")):
                flash("Provided password is incorrect.")
                return render_template('changepassword.html')

            elif newpassword != repeatpassword:
                flash("New password does not match with confirmation.")
                return render_template('changepassword.html')

            else:
                if passwordValidator(newpassword):
                    newPassHash = generate_password_hash(newpassword)
                    db.execute(f"UPDATE users SET hash=:hash WHERE id=:id", hash=newPassHash, id=user_id)
                    flash("Password successfully updated!")
                    return render_template('login.html')
                else:
                    flash("Password must be 10 chars length, have 2 digits, 2 letters, and special char.")
                    return render_template('changepassword.html')

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    currentlyLoggedIn = session.get("user_id")
    data = db.execute("SELECT * FROM purchases WHERE id=? GROUP BY stock", currentlyLoggedIn)
    freeFromNull = []
    for a in data:
        if a['qty_currently_owned'] != 0:
            freeFromNull.append(a)
    s = []
    s.append(freeFromNull[0]['stock'])
    for r in freeFromNull:
        if r['stock'] not in s:
            s.append(r['stock'])

    if request.method == "GET":
        return render_template("sell.html", stock=s)
    else:
        quantity = request.form.get('quantity')
        select = request.form.get('symbol')
        currentlyLoggedIn = session.get("user_id")
        currentlyOwnedStocks = db.execute("SELECT * FROM purchases WHERE id=?", currentlyLoggedIn)
        result = lookup(select)
        currentStockPrice = result['price']
        currentUser = session.get("user_id") # repeated!
        logged = db.execute("SELECT * FROM users WHERE id=?", currentUser)
        totalOfSharesToSell = 0
        totalOfSharesSold = 0
        arr = []
        arrSale = []
        for c in currentlyOwnedStocks:
            if c['stock'] == select:
                if c['type_of_transaction'] == 'Purchase' or c['type_of_transaction'] == 'purchase':
                    arr.append(int(c['qty_of_shares']))
                    updtdOwns = db.execute("SELECT qty_currently_owned FROM purchases WHERE stock=:select ORDER BY date DESC LIMIT 1", select=request.form.get("symbol"))
                    totalOfSharesToSell = updtdOwns[0]['qty_currently_owned']

                if c['type_of_transaction'] == 'sale' or c['type_of_transaction'] == 'Sale':
                    arrSale.append(int(c['qty_of_shares']))
                    totalOfSharesSold = sum(arrSale)  # 2

    mostRecent = db.execute("SELECT updated_ammount FROM purchases WHERE purchases.id=? ORDER BY date DESC LIMIT 1", currentlyLoggedIn)
    updatedValueOfStocksAfterSale = 0

    if totalOfSharesToSell >= int(quantity):
        updatedValueOfStocksAfterSale = totalOfSharesToSell - int(quantity)
        db.execute("INSERT INTO purchases(id,date,stock,current_value,stock_value,updated_ammount, qty_of_shares,  type_of_transaction, qty_currently_owned, value_of_holding)  VALUES(:id, :date, :stock, :current_value, :stock_value,:updated_ammount, :qty_of_shares,:type_of_transaction, :qty_currently_owned, :value_of_holding)", id=logged[0]['id'], date=datetime.datetime.now(), stock=select, current_value=round(mostRecent[0]['updated_ammount'],2), stock_value=currentStockPrice, updated_ammount=round(mostRecent[0]['updated_ammount'] + (currentStockPrice*int(quantity)),2), qty_of_shares=quantity, type_of_transaction="sale", qty_currently_owned=updatedValueOfStocksAfterSale, value_of_holding=round(updatedValueOfStocksAfterSale*currentStockPrice, 2))
    else:
        flash("Can't sell more stocks than those you currently have.")
        return render_template('sell.html', stock=s)

    flash("You completed your sale successfully.")
    return redirect("/")


def errorhandler(e):
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
