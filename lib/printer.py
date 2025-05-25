import fitz
from escpos.printer import Network
from PIL import Image, ImageFilter, ImageEnhance
import io

def print_pdf_on_thermal(
    pdf_path: str,
    printer_ip: str,
    printer_port: int = 9100,
    printer_width: int = 576,
    zoom: float = 2.0,
    threshold: int = 130,
    feed_lines: int = 1,
) -> None:
    """
    Render each page of a PDF and send it to an ESC/POS thermal printer.

    Args:
        pdf_path: Path to the source PDF file.
        printer_ip: IP address of the thermal printer.
        printer_port: Port of the thermal printer (default 9100).
        printer_width: Width in dots of the printer (default 576 for 80mm paper).
        zoom: Oversampling factor for rendering (2–3 recommended).
        threshold: Binarization threshold (0–255, lower = darker).
        feed_lines: Number of blank lines to feed before cutting.
    """
    # ESC/POS raw commands
    ESC_INIT = b"\x1b@"                  # initialize printer (reset margins)
    ESC_FEED_N = lambda n: b"\x1bd" + bytes([n])  # feed n lines
    ESC_ALIGN_L = b"\x1ba\x00"         # alignment: left

    # Open PDF and printer connection
    doc = fitz.open(pdf_path)
    printer = Network(printer_ip, printer_port)

    try:
        for page in doc:
            # 1) Render at zoom× resolution
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix)
            img = Image.open(io.BytesIO(pix.tobytes(output="png")))

            # 2) Convert to grayscale
            img = img.convert("L")

            # 3) Resize to printer width
            scale = printer_width / img.width
            new_height = int(img.height * scale)
            img = img.resize((printer_width, new_height), Image.LANCZOS)

            # 4) Smooth with mild blur
            img = img.filter(ImageFilter.GaussianBlur(radius=0.4))

            # 5) Enhance contrast
            img = ImageEnhance.Contrast(img).enhance(1.3)

            # 6) Binarize (black & white)
            img = img.point(lambda p: 0 if p < threshold else 255, mode="1")

            # 7) Send initialize, alignment, and image
            printer._raw(ESC_INIT)
            printer._raw(ESC_ALIGN_L)
            with io.BytesIO() as buf:
                img.save(buf, format="PNG")
                printer.image(io.BytesIO(buf.getvalue()))

            # 8) Feed blank lines
            printer._raw(ESC_FEED_N(feed_lines))

            # 9) Cut
            printer.cut()
    finally:
        printer.close()


