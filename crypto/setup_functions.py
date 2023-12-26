def create_empty_exchange_dict(prices, _dict, exchange):
    for ticker in prices:
        if "/" not in ticker:
            continue

        if ticker in _dict:
            _dict[ticker]["exchanges"][exchange] = {}
            continue

        _dict[ticker] = {"exchanges": {exchange: {}}}


def insert_exchange_market_details(markets, _dict, exchange):
    for ticker, values in markets.items():
        try:
            exc_dict = _dict[ticker]["exchanges"][exchange]
            exc_dict["symbol"] = values["symbol"]
            exc_dict["exchange"] = exchange
            exc_dict["base"] = values["base"]
            exc_dict["quote"] = values["quote"]
            exc_dict["active"] = values["active"]
            exc_dict["type"] = values["type"]
            exc_dict["expiry"] = values["expiry"]
            exc_dict["expiryDatetime"] = values["expiryDatetime"]
            exc_dict["taker"] = values["taker"]
            exc_dict["maker"] = values["maker"]
        except:
            continue


def insert_exchange_currency_details(currencies, _dict, exchange):
    for ticker in _dict:
        base = _dict[ticker]["exchanges"][exchange]["base"]

        try:
            currencyDetails = currencies[base]
            currencyDetails.pop("info", None)
            _dict[ticker]["exchanges"][exchange]["currencyDetails"] = currencyDetails
        except:
            continue


def insert_exchange_price_details(prices, _dict, exchange):
    for ticker, values in prices.items():
        try:
            exc_dict = _dict[ticker]["exchanges"][exchange]
            exc_dict["bid"] = values["bid"]
            exc_dict["ask"] = values["ask"]
            exc_dict["last"] = values["last"]
            exc_dict["previousClose"] = values["previousClose"]
            exc_dict["change"] = values["change"]
            exc_dict["percentage"] = values["percentage"]

            if values["baseVolume"] == None:
                exc_dict["baseVolume"] = values["quoteVolume"] / values["last"]
            else:
                exc_dict["baseVolume"] = values["baseVolume"]

            if values["quoteVolume"] == None:
                exc_dict["quoteVolume"] = values["baseVolume"] * values["last"]
            else:
                exc_dict["quoteVolume"] = values["quoteVolume"]

        except:
            continue


def find_best_exchange(exchanges):
    best_exchange = None
    volume = -1
    for exc in exchanges:
        if exchanges[exc]["baseVolume"] > volume:
            best_exchange = exc
            volume = exchanges[exc]["baseVolume"]

    return best_exchange


def define_best_exchanges_for_tickers(_dict):
    for ticker in _dict:
        exchanges = _dict[ticker]["exchanges"]
        best_exchange = find_best_exchange(exchanges)
        _dict[ticker]["exchange"] = best_exchange


def insert_common_details(_dict):
    for ticker, values in _dict.items():
        best_exchange = values["exchange"]
        values["symbol"] = values["exchanges"][best_exchange]["symbol"]
        values["base"] = values["exchanges"][best_exchange]["base"]
        values["quote"] = values["exchanges"][best_exchange]["quote"]
        values["type"] = values["exchanges"][best_exchange]["type"]
        values["price"] = values["exchanges"][best_exchange]["last"]
        values["change"] = values["exchanges"][best_exchange]["change"]
        values["percentage"] = values["exchanges"][best_exchange]["percentage"]
        values["baseVolume"] = values["exchanges"][best_exchange]["baseVolume"]
        values["quoteVolume"] = values["exchanges"][best_exchange]["quoteVolume"]
        values["totalBaseVolume"] = sum(
            [
                values["exchanges"][exc]["baseVolume"]
                for exc in values["exchanges"]
                if values["exchanges"][exc]["baseVolume"] != None
            ]
        )
        values["totalQuoteVolume"] = sum(
            [
                values["exchanges"][exc]["quoteVolume"]
                for exc in values["exchanges"]
                if values["exchanges"][exc]["quoteVolume"] != None
            ]
        )
