import os
import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        api_key = os.environ.get("API_KEY")
        response = requests.get(f"https://cloud-sse.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token={api_key}")
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()
        return {
            "name": quote["companyName"],
            "price": float(quote["latestPrice"]),
            "symbol": quote["symbol"]
        }
    except (KeyError, TypeError, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"


def getValueNow(stock):
    url = "https://cloud-sse.iexapis.com/stable/stock/{0}/quote?token=pk_cb048257d9d04ceea8a1a69ed655a042".format(stock)
    response = requests.get(url)
    data = response.json()
    return data['latestPrice']
fun = getValueNow

def passwordValidator(password):
    if len(password) < 10 or password.isdigit() or password.isalpha():
        return False
    digs = 0
    lets = 0
    hasSpecial = False

    for c in password:
        if c.isdigit():
            digs = digs+1
        if c.isalpha():
            lets = lets+1
        if c == '!' or c == '?' or c == '#' or c == '$' or c == '%' or  c == '&':
            hasSpecial = True
    if lets >= 2 and digs >=2 and hasSpecial:
        return True
    else:
        return False