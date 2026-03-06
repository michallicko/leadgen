# Sprint 16: Excel & Video Multimodal Processing

**Backlog items**: BL-267 (Excel), BL-268 (Video)
**Sprint**: 16
**Status**: Spec'd
**Dependencies**: BL-265 (PDF+Image, done in Sprint 14-15)

## Problem Statement

The multimodal pipeline supports PDF, Word, Image, and HTML. Two important
content types remain: spreadsheets (Excel/CSV) and video. Sales teams frequently
share pricing spreadsheets, competitive analyses in Excel, and product demo
videos. The agent needs to extract structured data from these formats.

## BL-267: Excel/CSV Processing

### User Stories

- As a sales user, I want to upload an Excel file so the agent can answer
  questions about its data.
- As a sales user, I want the agent to extract specific columns from a
  spreadsheet into a structured format for import.

### Acceptance Criteria

**AC-1: Sheet discovery**
- Given a multi-sheet Excel workbook
- When processed
- Then all sheet names are listed with row/column counts

**AC-2: Small sheet full conversion**
- Given a sheet with fewer than 50 rows
- When processed
- Then the full sheet is converted to a markdown table

**AC-3: Large sheet summary**
- Given a sheet with 50+ rows
- When processed
- Then a summary is generated with: column headers, row count, sample rows
  (first 5 + last 3), and basic stats (min/max/avg) on numeric columns

**AC-4: Schema-based extraction**
- Given a file_id and a schema definition `{fields: [{name, type, source_column?}]}`
- When `extract_data` tool is called
- Then returns `{rows: [...], unmapped_columns: [...], warnings: [...]}`

**AC-5: CSV support**
- Given a CSV file upload
- When processed
- Then treated identically to a single-sheet Excel file

**AC-6: Token budget**
- Given any spreadsheet
- When converted to markdown
- Then output is capped at 8000 characters with a truncation notice

### Technical Approach

**New file**: `api/services/multimodal/excel_processor.py`
- `openpyxl` for .xlsx reading (values only, no formulas)
- Python `csv` module for CSV files
- Strategy selection based on row count threshold (50)
- Stats computation with pure Python (no pandas dependency)

**New file**: `api/tools/excel_tools.py`
- `extract_data` tool registered with ToolRegistry
- Takes `{file_id, schema}`, returns structured JSON rows

**Dependencies**: `openpyxl` added to `requirements.txt`

### Data Model Changes

None. Uses existing `file_uploads` and `extracted_content` tables.

---

## BL-268: Video Processing

### User Stories

- As a sales user, I want to upload a product demo video so the agent can
  summarize what the product does.
- As a sales user, I want to paste a YouTube URL so the agent can analyze
  a competitor's demo.

### Acceptance Criteria

**AC-1: Audio transcription**
- Given a video file with audio
- When processed
- Then audio is extracted via ffmpeg and transcribed via OpenAI Whisper API

**AC-2: Keyframe extraction**
- Given a video file
- When processed
- Then keyframes are extracted via ffmpeg scene detection (threshold 0.3),
  capped at 1-3 frames per minute

**AC-3: Combined summary**
- Given transcript + keyframe descriptions
- When merged
- Then a time-aligned summary is produced with key moments

**AC-4: Cost estimate gate**
- Given a video before processing
- When cost is estimated
- Then estimated cost ($0.10-0.30 per 10 min) is shown before proceeding

**AC-5: Duration limit**
- Given a video longer than max_duration_minutes (default 15)
- When submitted
- Then processing is rejected with an error

**AC-6: URL support**
- Given a YouTube or Vimeo URL
- When submitted to analyze_video
- Then yt-dlp downloads the video first, then processes it

**AC-7: Caching**
- Given a previously processed video (by file hash)
- When requested again
- Then cached results are returned

### Technical Approach

**New file**: `api/services/multimodal/video_processor.py`
- `ffmpeg` (subprocess) for audio extraction + keyframe extraction
- OpenAI Whisper API for transcription (via `openai` client)
- Claude vision API for keyframe descriptions (via existing image_processor)
- `yt-dlp` (subprocess) for URL downloads
- Async pattern: returns job metadata, caller polls for completion
- File hash (SHA-256) for cache key

**New file**: `api/tools/video_tools.py`
- `analyze_video` tool registered with ToolRegistry
- Takes `{url_or_file_id, query, max_duration_minutes}`
- Returns `{transcript_summary, visual_summary, key_moments, cost_estimate}`

**Dependencies**: `yt-dlp` added to requirements.txt. `ffmpeg` and `openai` are
system/existing dependencies (ffmpeg must be installed on the host).

### Data Model Changes

None. Uses existing `file_uploads` and `extracted_content` tables.
Video results stored as `content_type='video_transcript'` and
`content_type='video_visual'` in `extracted_content`.

---

## Test Plan

### Unit Tests (BL-267)
- Sheet discovery on multi-sheet workbook (in-memory openpyxl)
- Small sheet full markdown conversion
- Large sheet summary with stats
- Schema-based extraction with mapping
- CSV file handling
- Token budget truncation
- Error handling (corrupt file, empty file)

### Unit Tests (BL-268)
- Video metadata extraction (mocked ffmpeg)
- Audio transcription (mocked Whisper API)
- Keyframe extraction (mocked ffmpeg)
- Cost estimation calculation
- Duration limit enforcement
- URL download (mocked yt-dlp)
- Cache hit/miss behavior
- Error handling (no audio track, ffmpeg not found)
