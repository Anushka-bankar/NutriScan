import test from 'node:test';
import assert from 'node:assert/strict';
import {
  cameraErrorMessage,
  isSupportedBarcode,
} from '../src/utils/barcodeScanner.js';

test('accepts supported barcode formats and rejects format-length mismatches', () => {
  assert.equal(isSupportedBarcode('5901234123457', 'EAN_13'), true);
  assert.equal(isSupportedBarcode('96385074', 'EAN_8'), true);
  assert.equal(isSupportedBarcode('012345678905', 'UPC_A'), true);
  assert.equal(isSupportedBarcode('5901234123457', 'EAN_8'), false);
  assert.equal(isSupportedBarcode('01234567890', 'UPC_A'), false);
  assert.equal(isSupportedBarcode('12345678901234'), false);
  assert.equal(isSupportedBarcode('1234abcd5678'), false);
});

test('explains camera permission, device, and secure-context failures', () => {
  assert.match(cameraErrorMessage('NotAllowedError'), /permission was denied/i);
  assert.match(cameraErrorMessage('NotFoundError'), /No camera was found/i);
  assert.match(cameraErrorMessage('NotReadableError'), /already in use/i);
  assert.match(cameraErrorMessage('SecurityError'), /secure page/i);
  assert.match(cameraErrorMessage('UnknownError'), /enter the barcode manually/i);
});
