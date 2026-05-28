# Doc 10: File Handling Architecture

## 1. Problem

When a user attaches a file (PDF resume, transcript, etc.) during form filling, the file serves **two distinct purposes**:

1. **Data source for the model** — the model reads the file content and extracts data to fill form fields (e.g., name, GPA, work history from a resume)
2. **Form attachment** — the file itself is a required form field value (e.g., "Upload your transcript")

These are different destinations (model vs. form/server) and they often happen simultaneously.

The challenge: different model backends have different file-handling capabilities. Claude can read PDFs natively via document content blocks. A small local model (Qwen 3.5 0.8B) can handle images but not raw PDF bytes. The file handling architecture must abstract this difference away so the rest of the application doesn't care which backend is active.

## 2. Design

### 2.1 ProcessedFile

A browser-side `FileProcessor` module reads the raw file and produces a `ProcessedFile` with **multiple representations**:

```
ProcessedFile {
  filename:      string
  mimeType:      string
  sizeBytes:     number
  base64:        string              // raw bytes (always produced)
  extractedText: string | null       // text from pdf.js (PDFs only)
  pageImages:    string[] | null     // per-page PNG data URLs (PDFs only, lazy)
}
```

- `base64` — always available. For form submission, this is the upload payload.
- `extractedText` — produced by pdf.js text extraction. For text-only and vision models alike, this is the primary way to send PDF content to small models. Also used as the prompt payload for our current dev flow (CLIProxyProvider).
- `pageImages` — produced by pdf.js canvas rendering. For vision-capable small models (Qwen 3.5 0.8B), PDF pages are rendered as images and sent as image content blocks. **Not needed initially** — built as a lazy capability.

### 2.2 Two Processing Functions

The FileProcessor has two distinct PDF processing functions:

| Function | Input | Output | Library | Use case |
|---|---|---|---|---|
| `pdfToText(file)` | PDF File | `extractedText` string | pdf.js `page.getTextContent()` | Text-only models, CLIProxy dev flow, logging |
| `pdfToImages(file)` | PDF File | `pageImages` array of PNG data URLs | pdf.js `page.render()` + canvas | Vision-capable small models (Qwen 3.5) |

Both use pdf.js (~1.5MB with worker), which is **lazy-loaded** — not bundled in the initial page load. The library is fetched on first file attachment.

### 2.3 Two Parallel Flows

```
User attaches file
       │
       ▼
  FileProcessor.process(file: File) → ProcessedFile
       │
       ├──→ [Flow A] Model input — ChatProvider.send(text, { files })
       │         Each provider picks the best representation:
       │         ├── CLIProxy (dev)      → extractedText prepended to prompt
       │         ├── API (Claude native) → base64 as document content block
       │         ├── Local text model    → extractedText injected into prompt
       │         └── Local vision model  → pageImages as image content blocks
       │
       └──→ [Flow B] Form attachment — if file matches a schema `file` field
                 ├── formValues[field_id] = { filename, sizeBytes, ... }
                 └── On submission: raw bytes sent to website/persistence server
```

**Flow A and Flow B are independent.** A file can be:
- Model input only (user drops a resume for extraction, but the form has no "resume" field)
- Form attachment only (user uploads a required document, but doesn't need the model to read it)
- Both (user uploads transcript → model extracts GPA → transcript also attached to `transcript` file field)

### 2.4 Provider Strategy Table

| Provider | PDF Strategy | What gets sent |
|---|---|---|
| CLIProxyProvider (current dev flow) | `pdfToText` | Extracted text prepended to prompt string |
| APIProvider (Claude API direct) | Native | `base64` as document content block |
| LocalModelProvider (text-only) | `pdfToText` | Extracted text injected into prompt |
| LocalModelProvider (vision) | `pdfToImages` | Page images as image content blocks |

### 2.5 Current Dev Flow (CLIProxyProvider)

For our immediate development needs, the flow is simple:

```
Browser                           Server                    Claude CLI
───────                           ──────                    ──────────
FileProcessor.process(pdf)
  → pdfToText() extracts text
  → ProcessedFile.extractedText

User clicks Send
  → prompt = "[File: Resume.pdf]\n{extractedText}\n\n---\n\n{userMessage}"
  → POST /api/generate { prompt }

                                  agent.run(prompt)
                                    → Claude CLI receives
                                      full text in prompt
                                                            Reads text, extracts
                                                            data, responds with
                                                            set_fields actions
```

**No server changes needed.** The extracted text is just part of the prompt string. The server remains a dumb proxy.

### 2.6 Form Attachment — Model-Driven Assignment

File-to-field assignment is **not done by the browser**. The browser cannot reliably determine whether a PDF is a resume, transcript, or statement of purpose just from the filename. Instead, the model reads the file content, identifies the document type, and assigns it.

**Flow:**

1. User attaches a file → browser processes it (text extraction for PDFs), shows a chip in the input area. **No form field assignment happens yet.**
2. User sends the message → extracted text goes to the model as part of the prompt.
3. Model reads the content, determines the document type, and uses `ask_choice` to confirm with the user (e.g., "This looks like a resume. Which document field should I assign it to?").
4. User confirms via the choice button.
5. Model uses `set_fields` to assign the file to the confirmed field (e.g., `{ field_id: "resume", value: "Resume.pdf" }`) and extracts data from the content.
6. Browser's `handleSetFields()` detects the file-type field, looks up the file in `sentFiles` by filename, stores metadata `{ filename, mimeType, sizeBytes }` in `formValues[field_id]`.
7. Section accordion updates to show "✓ Resume: uploaded" and section progress counters update.

No actual file upload to a persistence server — the draft just records that the file was attached. In a real deployment, the form submission endpoint on the target website would handle the actual file transfer. Our persistence server only stores draft/submission JSON with file metadata (filename, size, type), not the file bytes.

## 3. FileProcessor Module

`public/js/file-processor.js` — runs entirely in the browser.

```javascript
// Main entry point
FileProcessor.process(file: File) → Promise<ProcessedFile>

// PDF-specific functions (lazy-load pdf.js on first call)
FileProcessor.pdfToText(file: File) → Promise<string>
FileProcessor.pdfToImages(file: File, opts?: { scale?: number }) → Promise<string[]>
```

### Processing by file type

| File type | base64 | extractedText | pageImages |
|---|---|---|---|
| PDF | ✓ FileReader | ✓ pdf.js `getTextContent()` | Lazy, via `pdfToImages()` |
| Images (JPG, PNG) | ✓ FileReader | null | null (already an image) |
| Plain text (.txt, .csv) | ✓ FileReader | ✓ FileReader.readAsText() | null |

For unsupported types, `extractedText` is `null` and the provider must use `base64` or tell the user the file can't be read.

### pdf.js lazy loading

```javascript
let pdfjsLib = null;

async function loadPdfJs() {
  if (pdfjsLib) return pdfjsLib;
  pdfjsLib = await import('https://cdn.jsdelivr.net/npm/pdfjs-dist@4/build/pdf.min.mjs');
  pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@4/build/pdf.worker.min.mjs';
  return pdfjsLib;
}
```

The ~1.5MB library + worker are only fetched when the user first attaches a PDF. Subsequent attachments reuse the cached module.

### pdfToText implementation sketch

```javascript
async function pdfToText(file) {
  const pdf = await loadPdfJs();
  const arrayBuffer = await file.arrayBuffer();
  const doc = await pdf.getDocument({ data: arrayBuffer }).promise;

  const pages = [];
  for (let i = 1; i <= doc.numPages; i++) {
    const page = await doc.getPage(i);
    const content = await page.getTextContent();
    const text = content.items.map(item => item.str).join(' ');
    pages.push(text);
  }
  return pages.join('\n\n');
}
```

### pdfToImages implementation sketch

```javascript
async function pdfToImages(file, { scale = 1.5 } = {}) {
  const pdf = await loadPdfJs();
  const arrayBuffer = await file.arrayBuffer();
  const doc = await pdf.getDocument({ data: arrayBuffer }).promise;

  const images = [];
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');

  for (let i = 1; i <= doc.numPages; i++) {
    const page = await doc.getPage(i);
    const viewport = page.getViewport({ scale });
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    await page.render({ canvasContext: ctx, viewport }).promise;
    images.push(canvas.toDataURL('image/png'));
  }
  return images;
}
```

## 4. UX Flow

### Happy path: user uploads resume (current dev flow)

```
1. User clicks 📎, selects Resume.pdf
2. FileProcessor.process() runs:
   - Reads file as base64 (FileReader)
   - Lazy-loads pdf.js (first time only)
   - Extracts text via pdfToText()
   - Returns ProcessedFile { filename, mimeType, base64, extractedText, pageImages: null }
3. File chip appears in input area: "📄 Resume.pdf (245 KB)"
   (No auto-matching — file is NOT assigned to a form field yet)
4. User types "here's my resume" and clicks Send
5. Browser builds prompt:
   "[File: Resume.pdf]
    {extractedText}
    [End of Resume.pdf]

    here's my resume"
6. POST /api/generate { prompt } → server proxies to Claude CLI
7. Claude reads the extracted text, identifies it as a resume, responds:
   - Text: "I can see this is a resume. Let me confirm..."
   - Actions: ask_choice ["Resume / CV", "Official Transcript", "Statement of Purpose"]
8. User clicks "Resume / CV"
   → Frontend sends: [system] User selected option: "Resume / CV"
9. Claude responds:
   - Text: "Got it! I've assigned your resume and extracted your details."
   - Actions: set_fields [
       { resume: "Resume.pdf" },
       { full_name: "Jane Smith" },
       { email: "jane@example.com" },
       ...
     ]
10. Browser: handleSetFields detects "resume" is a file field →
    assignFileToField() looks up file in sentFiles, stores metadata.
    Section accordion updates: "✓ Resume: uploaded"
    Other fields stored in formValues, section progress counters update.
```

### System prompt: File Attachments section

The system prompt instructs the model to:
1. **Identify** the document type by reading its content
2. **Confirm** with the user via `ask_choice` which file field to assign it to
3. **After confirmation**, use `set_fields` to assign the file AND extract ALL matching data in one action
4. Summarize what was extracted and note what's still missing
5. Never invent data not explicitly present in the file

### Future: vision-capable local model

```
Steps 1-4 same as above.
5. FileProcessor.pdfToImages() renders pages to PNG
6. LocalModelProvider.send() receives text + files:
   - Builds message with image content blocks (one per page)
   - Sends to local WASM model
7. Model reads page images, extracts data (same actions as above)
```

## 5. Dependency Budget

| Dependency | Size (gzipped) | When loaded | Required for |
|---|---|---|---|
| pdf.js core | ~300 KB | First PDF attachment | `pdfToText`, `pdfToImages` |
| pdf.js worker | ~400 KB | First PDF attachment | Background processing |
| **Total** | **~700 KB** | **Lazy** | **PDF support** |

No dependency needed for images or plain text — those use built-in browser APIs.

Future (not now):
- tesseract-wasm (~2.1 MB) — OCR for scanned PDFs
- No DOCX support planned (users can export to PDF)

## 6. What This Does NOT Cover

- **File format conversion** (e.g., DOCX → text) — deferred until needed
- **OCR for scanned PDFs** — could add tesseract-wasm later, lazy-loaded
- **Large file handling** — base64 doubles the size; may need chunking for very large files
- **File encryption/DRM** — password-protected PDFs would fail extraction
- **Multi-file extraction merging** — if user uploads 3 files, each is processed independently; the model decides how to combine data

## 7. Related Documents

- **Doc 8: Architecture — Web App UX** — Browser-centric architecture, ChatProvider abstraction
- **Doc 9: Scenario Simulator** — Upload File as an action type in simulated scenarios
