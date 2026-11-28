"""Copy a PDFium RGB bitmap into independent packed bytes without Pillow.

This pure helper takes no PDF input, imports no native package and retains no
view of the bitmap buffer after the caller closes it.
"""


def packed_rgb(bitmap, expected):
    width, height = expected
    if (type(width) is not int or type(height) is not int or width <= 0 or height <= 0
            or (bitmap.width, bitmap.height) != expected):
        raise ValueError("Unexpected raster dimensions")
    if bitmap.mode != "RGB" or bitmap.n_channels != 3 or bitmap.rev_byteorder is not True:
        raise ValueError("Unexpected raster pixel format")
    row_size = width * 3
    stride = bitmap.stride
    if type(stride) is not int or stride < row_size:
        raise ValueError("Unexpected raster stride")
    with memoryview(bitmap.buffer) as buffer:
        if buffer.itemsize != 1 or buffer.ndim != 1 or not buffer.c_contiguous:
            raise ValueError("Unexpected raster buffer")
        if buffer.nbytes != stride * height:
            raise ValueError("Unexpected raster byte length")
        with buffer.cast("B") as pixels:
            result = (bytes(pixels) if stride == row_size else
                      b"".join(bytes(pixels[y * stride:y * stride + row_size])
                               for y in range(height)))
    if len(result) != row_size * height:
        raise ValueError("Unexpected raster byte length")
    if all(value == 255 for value in result):
        raise ValueError("Blank PDF raster")
    return result
