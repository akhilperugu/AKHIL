import { describe, expect, it } from 'vitest';
import { MAX_FILE_BYTES, validateImage } from './api';

describe('validateImage', () => {
  it('accepts supported image MIME types under the size limit', () => {
    expect(validateImage(new File(['label'], 'label.webp', { type: 'image/webp' }))).toBeNull();
  });

  it('rejects unsupported MIME types', () => {
    expect(validateImage(new File(['label'], 'label.svg', { type: 'image/svg+xml' }))).toContain('JPEG, PNG, or WebP');
  });

  it('rejects oversized and empty images', () => {
    expect(validateImage(new File([new Uint8Array(MAX_FILE_BYTES + 1)], 'large.png', { type: 'image/png' }))).toContain('10 MB');
    expect(validateImage(new File([], 'empty.png', { type: 'image/png' }))).toContain('empty');
  });
});
