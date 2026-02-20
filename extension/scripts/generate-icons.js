#!/usr/bin/env node
/**
 * Generate simple placeholder extension icons.
 * Creates colored squares with a "V" letter as PNG files.
 *
 * Usage: node scripts/generate-icons.js
 *
 * Uses Node.js built-in zlib for PNG compression.
 */

import { writeFileSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { deflateSync } from 'zlib';

const __dirname = dirname(fileURLToPath(import.meta.url));

// CRC32 lookup table
const crcTable = new Uint32Array(256);
for (let i = 0; i < 256; i++) {
  let c = i;
  for (let j = 0; j < 8; j++) {
    c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
  }
  crcTable[i] = c;
}

function crc32(buf) {
  let crc = 0xFFFFFFFF;
  for (let i = 0; i < buf.length; i++) {
    crc = crcTable[(crc ^ buf[i]) & 0xFF] ^ (crc >>> 8);
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

function makeChunk(type, data) {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length, 0);
  const typeBuffer = Buffer.from(type, 'ascii');
  const crc = crc32(Buffer.concat([typeBuffer, data]));
  const crcBuffer = Buffer.alloc(4);
  crcBuffer.writeUInt32BE(crc, 0);
  return Buffer.concat([length, typeBuffer, data, crcBuffer]);
}

function createPNG(width, height, pixels) {
  // PNG signature
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

  // IHDR chunk
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 2; // color type (RGB)
  ihdr[10] = 0; // compression
  ihdr[11] = 0; // filter
  ihdr[12] = 0; // interlace
  const ihdrChunk = makeChunk('IHDR', ihdr);

  // Build raw image data with filter bytes
  const rawData = Buffer.alloc(height * (1 + width * 3));
  for (let y = 0; y < height; y++) {
    const rowOffset = y * (1 + width * 3);
    rawData[rowOffset] = 0; // filter: None
    for (let x = 0; x < width; x++) {
      const srcIdx = (y * width + x) * 3;
      const dstIdx = rowOffset + 1 + x * 3;
      rawData[dstIdx] = pixels[srcIdx];
      rawData[dstIdx + 1] = pixels[srcIdx + 1];
      rawData[dstIdx + 2] = pixels[srcIdx + 2];
    }
  }

  // Compress with Node.js zlib
  const compressed = deflateSync(rawData);
  const idatChunk = makeChunk('IDAT', compressed);

  // IEND chunk
  const iendChunk = makeChunk('IEND', Buffer.alloc(0));

  return Buffer.concat([signature, ihdrChunk, idatChunk, iendChunk]);
}

// Draw a "V" on a colored background with rounded corners
function generateIcon(size, bgR, bgG, bgB, fgR, fgG, fgB) {
  const pixels = Buffer.alloc(size * size * 3);

  const radius = Math.max(1, Math.floor(size / 6));

  // Fill background
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const idx = (y * size + x) * 3;

      // Rounded corners check
      let isCorner = false;
      if (x < radius && y < radius) {
        isCorner = Math.hypot(x - radius, y - radius) > radius;
      } else if (x >= size - radius && y < radius) {
        isCorner = Math.hypot(x - (size - radius - 1), y - radius) > radius;
      } else if (x < radius && y >= size - radius) {
        isCorner = Math.hypot(x - radius, y - (size - radius - 1)) > radius;
      } else if (x >= size - radius && y >= size - radius) {
        isCorner = Math.hypot(x - (size - radius - 1), y - (size - radius - 1)) > radius;
      }

      if (isCorner) {
        // Transparent corners rendered as white
        pixels[idx] = 255;
        pixels[idx + 1] = 255;
        pixels[idx + 2] = 255;
      } else {
        pixels[idx] = bgR;
        pixels[idx + 1] = bgG;
        pixels[idx + 2] = bgB;
      }
    }
  }

  // Draw "V" letter
  const topY = Math.floor(size * 0.2);
  const bottomY = Math.floor(size * 0.8);
  const leftX = Math.floor(size * 0.2);
  const rightX = Math.floor(size * 0.8);
  const centerX = Math.floor(size / 2);
  const thickness = Math.max(1, Math.floor(size / 10));

  for (let y = topY; y <= bottomY; y++) {
    const progress = (y - topY) / (bottomY - topY);
    const xLeft = leftX + progress * (centerX - leftX);
    const xRight = rightX - progress * (rightX - centerX);

    for (let t = -thickness; t <= thickness; t++) {
      // Left stroke of V
      const px1 = Math.round(xLeft) + t;
      if (px1 >= 0 && px1 < size && y >= 0 && y < size) {
        const idx = (y * size + px1) * 3;
        pixels[idx] = fgR;
        pixels[idx + 1] = fgG;
        pixels[idx + 2] = fgB;
      }

      // Right stroke of V
      const px2 = Math.round(xRight) + t;
      if (px2 >= 0 && px2 < size && y >= 0 && y < size) {
        const idx = (y * size + px2) * 3;
        pixels[idx] = fgR;
        pixels[idx + 1] = fgG;
        pixels[idx + 2] = fgB;
      }
    }
  }

  return createPNG(size, size, pixels);
}

// Generate icons
const sizes = [16, 48, 128];

// Purple prod icons (#6E2C8B background, white text)
const prodDir = resolve(__dirname, '../src/icons/prod');
mkdirSync(prodDir, { recursive: true });
for (const size of sizes) {
  const png = generateIcon(size, 0x6E, 0x2C, 0x8B, 255, 255, 255);
  writeFileSync(resolve(prodDir, `${size}.png`), png);
  console.log(`Created prod/${size}.png (${png.length} bytes)`);
}

// Orange staging icons (#F97316 background, white text)
const stagingDir = resolve(__dirname, '../src/icons/staging');
mkdirSync(stagingDir, { recursive: true });
for (const size of sizes) {
  const png = generateIcon(size, 0xF9, 0x73, 0x16, 255, 255, 255);
  writeFileSync(resolve(stagingDir, `${size}.png`), png);
  console.log(`Created staging/${size}.png (${png.length} bytes)`);
}

console.log('All icons generated!');
