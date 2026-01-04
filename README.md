# GeoTagger

A Python command-line tool that reads GPS and datetime EXIF data from photos and overlays a location card on each image — showing a satellite map, reverse-geocoded address, coordinates, and timestamp. Designed as a stamped proof-of-visit for field surveys, site inspections, or travel documentation.

---

## How It Works

For each image in the input directory, GeoTagger:

1. Reads GPS coordinates and capture datetime from EXIF metadata
2. Reverse-geocodes the coordinates via the Google Geocoding API
3. Fetches a satellite map thumbnail via the Google Static Maps API
4. Composites a location card onto the bottom of the image
5. Re-embeds the original EXIF metadata into the output JPEG

If an image is missing GPS or datetime data, a fallback image can be supplied to substitute those values.

---

## Features

- Parallel batch processing with configurable worker threads
- SQLite geocode cache — avoids repeat API calls across runs for the same coordinates
- In-memory LRU cache — deduplicates API calls within a single run
- Thread-safe API call handling — prevents duplicate concurrent requests for identical coordinates
- Original EXIF metadata re-embedded into every output file
- Skips already-processed images on re-runs
- Graceful per-image error handling — one bad file never kills the batch

---

## Requirements

- Python 3.10 or higher
- A Google Cloud project with the following APIs enabled:
  - [Geocoding API](https://developers.google.com/maps/documentation/geocoding)
  - [Maps Static API](https://developers.google.com/maps/documentation/maps-static)

---

## Project Structure

```
GeoTagger/
├── src/
|   ├── main.py            # Entry point — batch processing and orchestration
|   ├── geo.py             # Geocoding, static map fetching, SQLite cache
|   ├── drawing.py         # Location card rendering
|   ├── exif_utils.py      # EXIF read/parse/validate utilities
|   ├── geocache.db        # Auto-created SQLite cache
|   └── .env               # Your API key
└── assets/
    ├── Inter_18pt-Bold.ttf
    ├── Inter_18pt-Regular.ttf
    └── marker.png     # Map pin overlaid on the satellite thumbnail
```

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/GeoTagger.git
cd GeoTagger/src
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install Pillow requests exifread piexif tqdm python-dotenv
```

### 4. Add your Google API key

Create a `.env` file in the project root:

```
GOOGLE_API_KEY=your_api_key_here
```

> Make sure both the **Geocoding API** and **Maps Static API** are enabled in your Google Cloud Console for this key.
---

## Usage

```bash
python main.py <input_dir> <output_dir> [--fallback <image>] [--workers <n>]
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `input_dir` | ✅ | Directory containing source images |
| `output_dir` | ✅ | Directory where tagged images will be saved |
| `--fallback` | ❌ | Path to an image with valid GPS/datetime EXIF, used as a fallback for images missing that data |
| `--workers` | ❌ | Number of parallel worker threads (default: `4`, recommended max: `8`) |
| `--suffix` | ❌ | Suffix appended to the output files (default: `_geotag`) |

### Examples

**Basic usage:**
```bash
python main.py photos/ output/
```

**With a fallback image for missing EXIF:**
```bash
python main.py photos/ output/ --fallback reference.jpg
```

**With 6 parallel workers:**
```bash
python main.py photos/ output/ --workers 6
```

**With suffix `_output`:**
```bash
python main.py photos/ output/ --suffix _output
```

**Full example:**
```bash
python main.py ./site_photos ./geotagged --fallback ./reference.jpg --workers 6 --suffix _output
```

---

## Output

Each output file is saved as `<original_name>_geotag.jpg` by default in the output directory (use `--suffix` to change the output suffix). The location card overlaid on the image contains:

- A rounded satellite map thumbnail of the capture location
- City, state, and country header
- Full reverse-geocoded address
- Latitude and longitude
- Day, date, time, and UTC offset from EXIF

Already-processed images are skipped automatically on re-runs.

---

## Caching

Geocode results are cached in two layers:

- **SQLite** (`geocache.db`) — persists across runs. Any coordinates already looked up in a previous session are served from the database with no API call.
- **LRU cache** — in-memory, deduplicates repeated lookups within a single run before they even reach SQLite.

Delete `geocache.db` to force fresh API lookups for all coordinates.

---

## Notes on API Usage

- Google's Geocoding and Static Maps APIs are **paid** beyond the free monthly credit. Each image that is a cache miss consumes one Geocoding call and one Static Maps call.
- Keep `--workers` at or below `8` to avoid hitting Google's per-second rate limits, which return `OVER_QUERY_LIMIT` errors.
- Rounding coordinates to 5 decimal places (~1.1m precision) before lookup maximises cache hit rates for images taken in close proximity.

---
