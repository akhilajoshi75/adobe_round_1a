# Adobe Hackathon Round 1A - Structured Outline Extractor

## Overview

This solution extracts a structured outline from PDF documents, including:
- Title
- Headings (H1, H2, H3) with page numbers

It is designed to run fully offline, quickly, and within the constraints provided by the challenge.

## Features

- Accepts input PDF files via `/app/input`
- Outputs structured JSON for each PDF in `/app/output`
- Supports clean title and heading detection using text layout and font-based heuristics
- Executes within 10 seconds for a 50-page PDF

## Requirements

- Docker (CPU-only)
- Compatible with `linux/amd64`

## Build

```bash
docker build --platform linux/amd64 -t outline-extractor-1a .
```

## Run

```bash
docker run --rm -v $(pwd)/input:/app/input -v $(pwd)/output:/app/output --network none outline-extractor-1a
```

## Output Format

Each output JSON follows this structure:

```json
{
  "title": "Document Title",
  "outline": [
    { "level": "H1", "text": "Heading One", "page": 1 },
    { "level": "H2", "text": "Subheading", "page": 2 },
    { "level": "H3", "text": "Sub-subheading", "page": 3 }
  ]
}
```

## Notes

- No API or internet access is used.
- No hardcoded logic or file-specific tweaks.
- Model size is zero (heuristic-based).
