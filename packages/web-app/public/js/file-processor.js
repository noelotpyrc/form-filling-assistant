/**
 * Browser-side file processor for the form-filling assistant.
 *
 * Reads user-attached files and produces ProcessedFile objects with multiple
 * representations (base64, extractedText, pageImages) so that different
 * ChatProvider backends can pick the best format for their model.
 *
 * Two PDF-specific functions:
 *   - pdfToText(file)   — text extraction via pdf.js getTextContent()
 *   - pdfToImages(file)  — page rendering to PNG via pdf.js canvas render
 *
 * pdf.js is lazy-loaded from CDN on first PDF attachment (~700 KB gzipped).
 *
 * Exported via window.FileProcessor
 */
(function () {
  'use strict';

  // ── pdf.js lazy loader ──

  var pdfjsLib = null;
  var pdfjsLoadPromise = null;

  var PDFJS_CDN = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@4.7.76/build/';

  function loadPdfJs() {
    if (pdfjsLib) return Promise.resolve(pdfjsLib);
    if (pdfjsLoadPromise) return pdfjsLoadPromise;

    // Dynamic import() works from non-module scripts in all modern browsers
    pdfjsLoadPromise = import(PDFJS_CDN + 'pdf.min.mjs').then(function (mod) {
      mod.GlobalWorkerOptions.workerSrc = PDFJS_CDN + 'pdf.worker.min.mjs';
      pdfjsLib = mod;
      return pdfjsLib;
    }).catch(function (err) {
      pdfjsLoadPromise = null; // allow retry
      throw new Error('Failed to load pdf.js: ' + err.message);
    });

    return pdfjsLoadPromise;
  }

  // ── PDF to Text ──

  /**
   * Extract text content from a PDF file using pdf.js.
   *
   * @param {File} file - A PDF File object
   * @returns {Promise<string>} Concatenated text from all pages
   */
  function pdfToText(file) {
    return loadPdfJs().then(function (pdf) {
      return file.arrayBuffer().then(function (arrayBuffer) {
        return pdf.getDocument({ data: arrayBuffer }).promise.then(function (doc) {
          var pagePromises = [];
          for (var i = 1; i <= doc.numPages; i++) {
            // IIFE to capture page number (avoid closure-in-loop bug with var)
            pagePromises.push((function (pageNum) {
              return doc.getPage(pageNum).then(function (page) {
                return page.getTextContent().then(function (content) {
                  return content.items.map(function (item) { return item.str; }).join(' ');
                });
              });
            })(i));
          }
          return Promise.all(pagePromises).then(function (pages) {
            return pages.join('\n\n');
          });
        });
      });
    });
  }

  // ── PDF to Images ──

  /**
   * Render each page of a PDF to a PNG data URL using pdf.js canvas rendering.
   *
   * @param {File} file - A PDF File object
   * @param {object} [opts] - Options
   * @param {number} [opts.scale=1.5] - Render scale factor
   * @returns {Promise<string[]>} Array of PNG data URLs, one per page
   */
  function pdfToImages(file, opts) {
    var scale = (opts && opts.scale) || 1.5;

    return loadPdfJs().then(function (pdf) {
      return file.arrayBuffer().then(function (arrayBuffer) {
        return pdf.getDocument({ data: arrayBuffer }).promise.then(function (doc) {
          var canvas = document.createElement('canvas');
          var ctx = canvas.getContext('2d');
          var images = [];

          // Render pages sequentially (canvas reuse)
          function renderPage(pageNum) {
            if (pageNum > doc.numPages) return Promise.resolve(images);
            return doc.getPage(pageNum).then(function (page) {
              var viewport = page.getViewport({ scale: scale });
              canvas.width = viewport.width;
              canvas.height = viewport.height;
              return page.render({ canvasContext: ctx, viewport: viewport }).promise.then(function () {
                images.push(canvas.toDataURL('image/png'));
                return renderPage(pageNum + 1);
              });
            });
          }

          return renderPage(1);
        });
      });
    });
  }

  // ── File reading helpers ──

  function readAsBase64(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () {
        // result is "data:<mime>;base64,<data>" — strip the prefix
        var base64 = reader.result.split(',')[1];
        resolve(base64);
      };
      reader.onerror = function () { reject(reader.error); };
      reader.readAsDataURL(file);
    });
  }

  function readAsText(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () { resolve(reader.result); };
      reader.onerror = function () { reject(reader.error); };
      reader.readAsText(file);
    });
  }

  // ── Main processor ──

  var PDF_TYPES = ['application/pdf'];
  var TEXT_TYPES = ['text/plain', 'text/csv', 'text/tab-separated-values'];
  var IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];

  /**
   * Process a user-attached file into a ProcessedFile with multiple representations.
   *
   * @param {File} file - The raw File object from <input type="file">
   * @returns {Promise<ProcessedFile>}
   *
   * @typedef {object} ProcessedFile
   * @property {string} filename
   * @property {string} mimeType
   * @property {number} sizeBytes
   * @property {string} base64         - Raw bytes as base64 (always present)
   * @property {string|null} extractedText - Text content (PDFs, text files)
   * @property {string[]|null} pageImages  - PNG data URLs per page (lazy, PDFs only)
   * @property {File} _file            - Original File reference (for re-processing)
   */
  function process(file) {
    var mimeType = file.type || 'application/octet-stream';
    var isPdf = PDF_TYPES.indexOf(mimeType) !== -1 || file.name.toLowerCase().endsWith('.pdf');
    var isText = TEXT_TYPES.indexOf(mimeType) !== -1 ||
      file.name.toLowerCase().endsWith('.txt') ||
      file.name.toLowerCase().endsWith('.csv');
    var isImage = IMAGE_TYPES.indexOf(mimeType) !== -1;

    var result = {
      filename: file.name,
      mimeType: mimeType,
      sizeBytes: file.size,
      base64: null,
      extractedText: null,
      pageImages: null,
      _file: file,
    };

    // Always read base64
    var base64Promise = readAsBase64(file).then(function (b64) {
      result.base64 = b64;
    });

    // Extract text based on type
    var textPromise;
    if (isPdf) {
      textPromise = pdfToText(file).then(function (text) {
        result.extractedText = text;
      }).catch(function (err) {
        console.warn('FileProcessor: PDF text extraction failed:', err.message);
        result.extractedText = null;
      });
    } else if (isText) {
      textPromise = readAsText(file).then(function (text) {
        result.extractedText = text;
      });
    } else {
      textPromise = Promise.resolve();
    }

    // pageImages are NOT produced eagerly — call pdfToImages(file) separately when needed

    return Promise.all([base64Promise, textPromise]).then(function () {
      return result;
    });
  }

  // ── Export ──
  window.FileProcessor = {
    process: process,
    pdfToText: pdfToText,
    pdfToImages: pdfToImages,
  };
})();
