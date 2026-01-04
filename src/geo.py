from functools import lru_cache
import requests
from requests.adapters import HTTPAdapter, Retry
import os
import threading
import sqlite3

session = requests.Session()
retries = Retry(total=3, backoff_factor=0.5,
                status_forcelist=[500,502,503,504])
session.mount('https://', HTTPAdapter(max_retries=retries))

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "geocache.db")
_db_local = threading.local()

def _get_db() -> sqlite3.Connection:
    """Return a per-thread SQLite connection, creating it and the schema if needed."""
    if not hasattr(_db_local, "con"):
        con = sqlite3.connect(_DB_PATH)
        con.execute("""
            CREATE TABLE IF NOT EXISTS geocache (
                lat  REAL,
                lon  REAL,
                header_addr TEXT NOT NULL,
                addr        TEXT NOT NULL,
                PRIMARY KEY (lat, lon)
            )
        """)
        con.commit()
        _db_local.con = con
    return _db_local.con

def _db_get(lat: float, lon: float):
    """Return (header_addr, addr) from SQLite, or None on a miss."""
    row = _get_db().execute(
        "SELECT header_addr, addr FROM geocache WHERE lat=? AND lon=?",
        (lat, lon)
    ).fetchone()
    return (row[0], row[1]) if row else None

def _db_set(lat: float, lon: float, headerAddrLine: str, addrLine: str):
    """Insert a new geocache entry, ignoring conflicts (same coords, two threads)."""
    con = _get_db()
    con.execute(
        "INSERT OR IGNORE INTO geocache (lat, lon, header_addr, addr) VALUES (?, ?, ?, ?)",
        (lat, lon, headerAddrLine, addrLine)
    )
    con.commit()

def fetch_geocode_json(lat, lon, apiKey):
    baseUrl = "https://maps.google.com/maps/api/geocode/json"
    params = {
        'latlng':f"{lat},{lon}",
        'key': apiKey
    }

    response = session.get(baseUrl, params=params, timeout=10)
    data = response.json()
    
    if data['status'] != 'OK':
        raise Exception(data.get('error_message', f"Geocode status: {data['status']}"))
    return data

@lru_cache(maxsize=256)
def get_addresses(lat, lon, apiKey):
    """Resolve (lat, lon) → (headerAddrLine, addrLine).
    Checks SQLite first, falls back to Google API on a miss.
    lru_cache deduplicates within a single run; SQLite persists across runs.
    """
    cached = _db_get(lat, lon)
    if cached:
        return cached

    data = fetch_geocode_json(lat, lon, apiKey)
    headerAddrLine, addrLine = get_addresses_from_json(data)
    _db_set(lat, lon, headerAddrLine, addrLine)
    return headerAddrLine, addrLine

@lru_cache(maxsize=128)
def fetch_map_image(lat, lon, apiKey, zoom=20, size=600, maptype="satellite", imgFormat='JPEG'):
    baseUrl = "https://maps.googleapis.com/maps/api/staticmap"
    params = {
        'center': f"{lat},{lon}",
        'zoom': zoom,
        'size': f"{size}x{size}",
        'maptype': maptype,
        'key': apiKey,
        # 'markers':f"color:red|{lat},{lon}",
        'format':imgFormat
    }
    response = session.get(baseUrl, params=params, timeout=10)
    
    if response.status_code != 200:
        raise Exception(response.status_code)

    return response.content

def get_addresses_from_json(data):
    result = data['results'][0]
    addrLine = result['formatted_address']

    # Variables for City Priority
    cityCandidates = {
        'loc':None,      #locality
        'sub':None,      #sublocality
        'admin2':None   #administrative_area_level_2
    }

    headerAddress = {
        'country':None,
        'state':None,
        'city':None
        }

    for component in result['address_components']:
        types = component['types']
        value = component['long_name']
        
        if 'country' in types:
            headerAddress['country'] = value

        if 'administrative_area_level_1' in types:
            headerAddress['state'] = value

        if 'locality' in types:
            cityCandidates['loc'] = value
        elif 'sublocality' in types or 'sublocality_level_1' in types:
            cityCandidates['sub'] = value
        elif 'administrative_area_level_2' in types:
            cityCandidates['admin2'] = value

    if cityCandidates['loc']:
        headerAddress['city'] = cityCandidates['loc']
    elif cityCandidates['sub']:
        headerAddress['city'] = cityCandidates['sub']
    elif cityCandidates['admin2']:
        headerAddress['city'] = cityCandidates['admin2']
        
    headerAddrLine = f"{headerAddress['city']}, {headerAddress['state']}, {headerAddress['country']}"

    return headerAddrLine, addrLine