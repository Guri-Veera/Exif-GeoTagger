import exifread
from datetime import datetime
import piexif

class NoGPSDataFound(Exception):
    def __init__(self, msg):
        super().__init__(msg)

class NoDateFound(Exception):
    def __init__(self, msg):
        super().__init__(msg)


def get_exif(imgPath):
    with open(imgPath, 'rb') as f:
        return exifread.process_file(f)
    
def get_piexif_bytes(imgPath):
    """Read raw EXIF bytes from the source image using piexif, for re-embedding into output."""
    try:
        return piexif.dump(piexif.load(imgPath))
    except Exception as e:
        print(f"[ERROR] {imgPath}: {e}")
        return None
    
def parse_gps_data(tags):
    lat = tags['GPS GPSLatitude'].values
    lon = tags['GPS GPSLongitude'].values
    latRef = tags['GPS GPSLatitudeRef'].values
    lonRef = tags['GPS GPSLongitudeRef'].values

    return convert_coords(lat, lon, latRef, lonRef)

def parse_date_time(tags):
    exifOffset = tags.get('EXIF OffsetTimeOriginal', '+00:00').values
    exifDate = tags['EXIF DateTimeOriginal'].values

    dt = datetime.strptime(exifDate, '%Y:%m:%d %H:%M:%S')
    dt = dt.strftime('%A, %d/%m/%Y %I:%M:%S %p')
    dt = f"{dt} GMT {exifOffset}"
    return dt

def validate_gps(tags):
    required = [
        'GPS GPSLatitude',
        'GPS GPSLongitude',
        'GPS GPSLatitudeRef',
        'GPS GPSLongitudeRef'
    ]
    if not all(tag in tags for tag in required):
        raise NoGPSDataFound("No GPS data found")

def validate_date(tags):
    required = [
        'EXIF DateTimeOriginal',
        'EXIF OffsetTimeOriginal'
    ]
    if not all(tag in tags for tag in required):
        raise NoDateFound("No DateTime data found")
    
def degrees_to_decimal(coordinate, ref):
    d = float(coordinate[0])
    m = float(coordinate[1])
    s = float(coordinate[2])

    decimal = d + (m / 60) + (s / 3600)
    if ref == "S" or ref == "W":
        decimal = -decimal
    return decimal

def convert_coords(lat, lon, latRef, lonRef):
    return (degrees_to_decimal(lat, latRef), degrees_to_decimal(lon, lonRef))