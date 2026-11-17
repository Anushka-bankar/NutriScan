const FORMAT_LENGTHS = {
  EAN_13: 13,
  EAN_8: 8,
  UPC_A: 12,
};

export function isSupportedBarcode(value, format = null) {
  const barcode = String(value || '').trim();
  if (!/^\d+$/.test(barcode)) return false;
  if (format && FORMAT_LENGTHS[format]) {
    return barcode.length === FORMAT_LENGTHS[format];
  }
  return Object.values(FORMAT_LENGTHS).includes(barcode.length);
}

export function cameraErrorMessage(name) {
  if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
    return 'Camera permission was denied. Allow camera access in your browser settings or enter the barcode manually.';
  }
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
    return 'No camera was found. Connect a camera or enter the barcode manually.';
  }
  if (name === 'NotReadableError' || name === 'TrackStartError') {
    return 'The camera is already in use or unavailable. Close other camera apps and try again.';
  }
  if (name === 'SecurityError') {
    return 'Camera scanning requires a secure page. Use localhost or HTTPS.';
  }
  return 'Could not start the camera. Check browser permissions or enter the barcode manually.';
}
