import io
import struct

_UNIT_KM = -3
_UNIT_100M = -2
_UNIT_10M = -1
_UNIT_1M = 0
_UNIT_10CM = 1
_UNIT_CM = 2
_UNIT_MM = 3
_UNIT_0_1MM = 4
_UNIT_0_01MM = 5
_UNIT_UM = 6
_UNIT_INCH = 6

_TIFF_TYPE_SIZES = {
    1: 1,
    2: 1,
    3: 2,
    4: 4,
    5: 8,
    6: 1,
    7: 1,
    8: 2,
    9: 4,
    10: 8,
    11: 4,
    12: 8,
}


def _convert_to_dpi(density, unit):
    if unit == _UNIT_KM:
        return int(density * 0.0000254 + 0.5)
    elif unit == _UNIT_100M:
        return int(density * 0.000254 + 0.5)
    elif unit == _UNIT_10M:
        return int(density * 0.00254 + 0.5)
    elif unit == _UNIT_1M:
        return int(density * 0.0254 + 0.5)
    elif unit == _UNIT_10CM:
        return int(density * 0.254 + 0.5)
    elif unit == _UNIT_CM:
        return int(density * 2.54 + 0.5)
    elif unit == _UNIT_MM:
        return int(density * 25.4 + 0.5)
    elif unit == _UNIT_0_1MM:
        return density * 254
    elif unit == _UNIT_0_01MM:
        return density * 2540
    elif unit == _UNIT_UM:
        return density * 25400
    return density


def get_from_file_stream(stream):
    height = -1
    width = -1
    head = stream.read(24)
    size = len(head)
    # handle GIFs
    if size >= 10 and head[:6] in (b'GIF87a', b'GIF89a'):
        # Check to see if content_type is correct
        try:
            width, height = struct.unpack("<hh", head[6:10])
        except struct.error:
            raise ValueError("Invalid GIF file")
    # see png edition spec bytes are below chunk length then and finally the
    elif size >= 24 and head.startswith(b'\211PNG\r\n\032\n') and head[12:16] == b'IHDR':
        try:
            width, height = struct.unpack(">LL", head[16:24])
        except struct.error:
            raise ValueError("Invalid PNG file")
    # Maybe this is for an older PNG version.
    elif size >= 16 and head.startswith(b'\211PNG\r\n\032\n'):
        # Check to see if we have the right content type
        try:
            width, height = struct.unpack(">LL", head[8:16])
        except struct.error:
            raise ValueError("Invalid PNG file")
    # handle JPEGs
    elif size >= 2 and head.startswith(b'\377\330'):
        try:
            stream.seek(0)  # Read 0xff next
            size = 2
            ftype = 0
            while not 0xc0 <= ftype <= 0xcf or ftype in [0xc4, 0xc8, 0xcc]:
                stream.seek(size, 1)
                byte = stream.read(1)
                while ord(byte) == 0xff:
                    byte = stream.read(1)
                ftype = ord(byte)
                size = struct.unpack('>H', stream.read(2))[0] - 2
            # We are at a SOFn block
            stream.seek(1, 1)  # Skip `precision' byte.
            height, width = struct.unpack('>HH', stream.read(4))
        except struct.error:
            raise ValueError("Invalid JPEG file")
    # handle JPEG2000s
    elif size >= 12 and head.startswith(b'\x00\x00\x00\x0cjP  \r\n\x87\n'):
        stream.seek(48)
        try:
            height, width = struct.unpack('>LL', stream.read(8))
        except struct.error:
            raise ValueError("Invalid JPEG2000 file")
    # handle big endian TIFF
    elif size >= 8 and head.startswith(b"\x4d\x4d\x00\x2a"):
        offset = struct.unpack('>L', head[4:8])[0]
        stream.seek(offset)
        ifdsize = struct.unpack(">H", stream.read(2))[0]
        for i in range(ifdsize):
            tag, datatype, count, data = struct.unpack(">HHLL", stream.read(12))
            if tag == 256:
                if datatype == 3:
                    width = int(data / 65536)
                elif datatype == 4:
                    width = data
                else:
                    raise ValueError("Invalid TIFF file: width column data type should be SHORT/LONG.")
            elif tag == 257:
                if datatype == 3:
                    height = int(data / 65536)
                elif datatype == 4:
                    height = data
                else:
                    raise ValueError("Invalid TIFF file: height column data type should be SHORT/LONG.")
            if width != -1 and height != -1:
                break
        if width == -1 or height == -1:
            raise ValueError("Invalid TIFF file: width and/or height IDS entries are missing.")
    elif size >= 8 and head.startswith(b"\x49\x49\x2a\x00"):
        offset = struct.unpack('<L', head[4:8])[0]
        stream.seek(offset)
        ifdsize = struct.unpack("<H", stream.read(2))[0]
        for i in range(ifdsize):
            tag, datatype, count, data = struct.unpack("<HHLL", stream.read(12))
            if tag == 256:
                width = data
            elif tag == 257:
                height = data
            if width != -1 and height != -1:
                break
        if width == -1 or height == -1:
            raise ValueError("Invalid TIFF file: width and/or height IDS entries are missing.")
    return width, height


def get_dpi_from_file_stream(stream):
    """
    Return (width, height) for a given img file content
    no requirements
    """
    x_dpi = -1
    y_dpi = -1
    head = stream.read(24)
    size = len(head)
    # handle GIFs
    # GIFs doesn't have density
    if size >= 10 and head[:6] in (b'GIF87a', b'GIF89a'):
        pass
    # see png edition spec bytes are below chunk length then and finally the
    elif size >= 24 and head.startswith(b'\211PNG\r\n\032\n'):
        chunk_offset = 8
        chunk = head[8:]
        while True:
            chunk_type = chunk[4:8]
            if chunk_type == b'pHYs':
                try:
                    x_density, y_density, unit = struct.unpack(">LLB", chunk[8:])
                except struct.error:
                    raise ValueError("Invalid PNG file")
                if unit:
                    x_dpi = _convert_to_dpi(x_density, _UNIT_1M)
                    y_dpi = _convert_to_dpi(y_density, _UNIT_1M)
                else:  # no unit
                    x_dpi = x_density
                    y_dpi = y_density
                break
            elif chunk_type == b'IDAT':
                break
            else:
                try:
                    data_size, = struct.unpack(">L", chunk[0:4])
                except struct.error:
                    raise ValueError("Invalid PNG file")
                chunk_offset += data_size + 12
                stream.seek(chunk_offset)
                chunk = stream.read(17)
    # handle JPEGs
    elif size >= 2 and head.startswith(b'\377\330'):
        try:
            stream.seek(0)  # Read 0xff next
            size = 2
            ftype = 0
            while not 0xc0 <= ftype <= 0xcf:
                if ftype == 0xe0:  # APP0 marker
                    stream.seek(7, 1)
                    unit, x_density, y_density = struct.unpack(">BHH", stream.read(5))
                    if unit == 1 or unit == 0:
                        x_dpi = x_density
                        y_dpi = y_density
                    elif unit == 2:
                        x_dpi = _convert_to_dpi(x_density, _UNIT_CM)
                        y_dpi = _convert_to_dpi(y_density, _UNIT_CM)
                    break
                stream.seek(size, 1)
                byte = stream.read(1)
                while ord(byte) == 0xff:
                    byte = stream.read(1)
                ftype = ord(byte)
                size = struct.unpack('>H', stream.read(2))[0] - 2
        except struct.error:
            raise ValueError("Invalid JPEG file")
    # handle JPEG2000s
    elif size >= 12 and head.startswith(b'\x00\x00\x00\x0cjP  \r\n\x87\n'):
        stream.seek(32)
        # skip JP2 image header box
        header_size = struct.unpack('>L', stream.read(4))[0] - 8
        stream.seek(4, 1)
        found_res_box = False
        try:
            while header_size > 0:
                print("header_size", header_size)
                box_header = stream.read(8)
                box_type = box_header[4:]
                print(box_type)
                if box_type == 'res ':  # find resolution super box
                    found_res_box = True
                    header_size -= 8
                    print("found res super box")
                    break
                print("@1", box_header)
                box_size, = struct.unpack('>L', box_header[:4])
                print("box_size", box_size)
                stream.seek(box_size - 8, 1)
                header_size -= box_size
            if found_res_box:
                while header_size > 0:
                    box_header = stream.read(8)
                    box_type = box_header[4:]
                    print(box_type)
                    if box_type == 'resd':  # Display resolution box
                        print("@2")
                        y_density, x_density, y_unit, x_unit = struct.unpack(">HHBB", stream.read(10))
                        x_dpi = _convert_to_dpi(x_density, x_unit)
                        y_dpi = _convert_to_dpi(y_density, y_unit)
                        break
                    box_size, = struct.unpack('>L', box_header[:4])
                    print("box_size", box_size)
                    stream.seek(box_size - 8, 1)
                    header_size -= box_size
        except struct.error as e:
            print(e)
            raise ValueError("Invalid JPEG2000 file")
    return x_dpi, y_dpi


def get(filepath):
    """
    Return (width, height) for a given img file content
    no requirements
    """
    with open(filepath, 'rb') as file:
        width, height = get_from_file_stream(file)
    return width, height


def get_from_bytes(file_content):
    """
    Return (width, height) for a given img content (bytes)
    no requirements
    """
    with io.BytesIO(file_content) as file_content:
        width, height = get_from_file_stream(file_content)
    return width, height


def get_dpi(filepath):
    """
    Return (x_dpi, y_dpi) for a given img file content
    no requirements
    """
    with open(filepath, 'rb') as file:
        x_dpi, y_dpi = get_dpi_from_file_stream(file)
    return x_dpi, y_dpi


def get_dpi_from_bytes(file_content):
    """
    Return (x_dpi, y_dpi) for a given img content (bytes)
    no requirements
    """
    with io.BytesIO(file_content) as file_content:
        x_dpi, y_dpi = get_dpi_from_file_stream(file_content)
    return x_dpi, y_dpi


def getDPI(filepath):
    from warnings import warn

    warn("`getDPI` is renamed to `get_dpi`. Use it instead",
         DeprecationWarning,
         stacklevel=2)
    return get_dpi(filepath)


def getDPI_from_bytes(file_content):
    from warnings import warn

    warn("`getDPI_from_bytes` is renamed to `get_dpi_from_bytes`. Use it instead",
         DeprecationWarning,
         stacklevel=2)
    return get_dpi_from_bytes(file_content)
