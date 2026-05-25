import requests
import pandas as pd

_cache = None  # avoid downloading the list repeatedly in same session


def get_instrument_list():
    """Download AngelOne's full NSE instrument master list."""
    global _cache
    if _cache is not None:
        return _cache

    url  = ("https://margincalculator.angelbroking.com"
            "/OpenAPI_File/files/OpenAPIScripMaster.json")
    data = requests.get(url, timeout=10).json()
    df   = pd.DataFrame(data)
    df   = df[df["exch_seg"] == "NSE"].copy()
    df.reset_index(drop=True, inplace=True)
    _cache = df
    return df


def get_token(symbol):
    """
    Return (token, trading_symbol) for a given NSE stock name.
    Example: get_token("RELIANCE") → ("2885", "RELIANCE-EQ")
    """
    df    = get_instrument_list()
    match = df[df["name"] == symbol]

    if match.empty:
        raise ValueError(
            f"Symbol '{symbol}' not found. "
            f"Check spelling or search with search_symbol()."
        )

    row = match.iloc[0]
    return str(row["token"]), str(row["symbol"])


def search_symbol(query):
    """Search for symbols containing a keyword — useful for discovering tokens."""
    df = get_instrument_list()
    return df[df["name"].str.contains(query, case=False, na=False)][
        ["token", "name", "symbol", "lotsize"]
    ].head(20)


if __name__ == "__main__":
    # Quick test — search and look up a token
    print("=== Searching for RELIANCE ===")
    print(search_symbol("RELIANCE").to_string())

    print("\n=== Token lookup ===")
    token, sym = get_token("RELIANCE")
    print(f"Name: RELIANCE  →  Token: {token}  Symbol: {sym}")