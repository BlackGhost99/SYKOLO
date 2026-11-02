"""Generate QR images locally without relying on third-party QR web services."""
import base64
from io import BytesIO
import qrcode
from qrcode.image.svg import SvgPathImage


def make_qr_data_uri(otpauth_uri):
    qr = qrcode.make(otpauth_uri, image_factory=SvgPathImage, box_size=8, border=4)
    stream = BytesIO()
    qr.save(stream)
    return "data:image/svg+xml;base64," + base64.b64encode(stream.getvalue()).decode("ascii")
