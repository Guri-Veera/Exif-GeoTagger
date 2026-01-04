from drawing import *
from geo import *
from exif_utils import *

from io import BytesIO
from PIL import Image
import os
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from tqdm import tqdm
import piexif
import traceback

from dotenv import load_dotenv
load_dotenv()

_geo_locks: dict[tuple, Lock] = {}
_geo_locks_lock = Lock()

def _get_geo_lock(key: tuple) -> Lock:
    with _geo_locks_lock:
        if key not in _geo_locks:
            _geo_locks[key] = Lock()
        return _geo_locks[key]

def fetch_geo_safe(lat, lon, apiKey):
    key = (lat, lon)
    with _get_geo_lock(key):
        return get_addresses(lat, lon, apiKey)

def fetch_map_safe(lat, lon, apiKey):
    key = (lat, lon, "map")
    with _get_geo_lock(key):
        return fetch_map_image(lat, lon, apiKey)
    
def process_image(filename, INPUT_DIR, OUTPUT_DIR, fallbackTags, apiKey, marker, progress_bar, SUFFIX):
    outPath = os.path.join(OUTPUT_DIR, os.path.splitext(filename)[0] + SUFFIX + ".jpg")
    if os.path.exists(outPath):
        return
    
    filePath = os.path.join(INPUT_DIR, filename)

    try:
        exifTags = get_exif(filePath)

        try:
            validate_gps(exifTags)
        except NoGPSDataFound:
            tqdm.write(f"[WARN] No GPS in {os.path.basename(filePath)} → using fallback GPS")
            exifTags['GPS GPSLatitude'] = fallbackTags['GPS GPSLatitude']
            exifTags['GPS GPSLongitude'] = fallbackTags['GPS GPSLongitude']
            exifTags['GPS GPSLatitudeRef'] = fallbackTags['GPS GPSLatitudeRef']
            exifTags['GPS GPSLongitudeRef'] = fallbackTags['GPS GPSLongitudeRef']
        
        try:
            validate_date(exifTags)
        except NoDateFound:
            tqdm.write(f"[WARN] No Date in {os.path.basename(filePath)} → using fallback Date")
            exifTags['EXIF DateTimeOriginal'] = fallbackTags['EXIF DateTimeOriginal']
            exifTags['EXIF OffsetTimeOriginal'] = fallbackTags['EXIF OffsetTimeOriginal']

        # ---------- GPS ----------
        lat, lon = parse_gps_data(exifTags)
        lat, lon = round(lat, 5), round(lon, 5)
        locText = f"Lat {lat}°, Long {lon}°"

        # ---------- Date/time (always from current image) ----------
        dateText = parse_date_time(exifTags)

        # ---------- Reverse geocode ----------
        headerAddrLine, addrLine = fetch_geo_safe(lat, lon, apiKey)

        # ---------- Map image ----------
        mapImg = fetch_map_safe(lat, lon, apiKey)
        map_img = Image.open(BytesIO(mapImg)).convert("RGBA")


        pasteX = map_img.width // 2 - marker.width // 2
        pasteY = map_img.height // 2 - marker.height
        map_img.paste(marker, (pasteX, pasteY), mask=marker)

        # ---------- Base image ----------
        img = Image.open(filePath)
        imgW, imgH = img.size

        # ---------- Card ----------
        card = create_location_card(
            imgW, imgH,
            map_img,
            headerAddrLine,
            addrLine,
            locText,
            dateText
        )

        # ---------- Composite ----------
        img.paste(card, (imgW // 2 - card.width // 2, imgH - card.height - imgH // 40), mask=card)
        exif_bytes = get_piexif_bytes(filePath)
        img.convert("RGB").save(outPath, format="JPEG")

        if exif_bytes:
            piexif.insert(exif_bytes, outPath)

        tqdm.write(f"[OK] Saved → {outPath}")
        
    except Exception as e:
        tqdm.write(f"[ERROR] {filename}: {e}")
        traceback.print_exc()
        raise

    finally:
        progress_bar.update(1) 

def main():
    parser = argparse.ArgumentParser(description="Geotag images with EXIF data and Google Maps")
    parser.add_argument("input_dir", help="Directory of images to process")
    parser.add_argument("output_dir", help="Directory to save geotagged images")
    parser.add_argument("--fallback", help="Image with valid EXIF to use as fallback")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers (default: 4)")
    parser.add_argument("--suffix", default='_geotag', help="Suffix appended to the output files (default: _geotag)")
    args = parser.parse_args()

    SUFFIX = args.suffix
    INPUT_DIR = args.input_dir
    OUTPUT_DIR = args.output_dir
    FALLBACK_GPS_IMAGE = args.fallback
    fallbackTags = get_exif(FALLBACK_GPS_IMAGE) if FALLBACK_GPS_IMAGE else {}

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    apiKey = os.getenv("GOOGLE_API_KEY")
    if not apiKey:
        raise EnvironmentError("GOOGLE_API_KEY not set in environment or .env file")

    image_exts = (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG")

    marker = Image.open("../assets/marker.png").convert("RGBA")
    marker = marker.resize((marker.width // 4, marker.height // 4))

    filenames = [
        f for f in os.listdir(INPUT_DIR)
        if f.lower().endswith(image_exts)
        and not os.path.exists(os.path.join(OUTPUT_DIR, os.path.splitext(f)[0] + SUFFIX + ".jpg"))
    ]

    with tqdm(total=len(filenames), desc="Geotagging", unit="img") as progress_bar:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [
                executor.submit(
                    process_image,
                    filename, INPUT_DIR, OUTPUT_DIR,
                    fallbackTags, apiKey, marker, progress_bar, SUFFIX
                )
                for filename in filenames
            ]
            for future in as_completed(futures):
                future.result()


if __name__ == "__main__":
    main()