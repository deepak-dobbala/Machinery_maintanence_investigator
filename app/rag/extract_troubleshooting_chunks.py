#!/usr/bin/env python3
"""
Maintenance Investigator
Haas VF Series troubleshooting chunk extractor.

Sources:
  96-8100 Rev C, June 2001
  96-8100 Rev E, June 2002

Output:
  upload/maintenance_investigator_troubleshooting_chunks.json
  upload/maintenance_investigator_troubleshooting_chunks.csv

This script:
1. Extracts PDF text using pypdf.
2. Locates Section 1 TROUBLESHOOTING robustly despite PDF line breaks.
3. Stops before Section 2 ALARMS.
4. Splits troubleshooting material around likely headings.
5. Keeps source-derived text intact.
6. Tags chunks by diagnostic topic/subsystem.
7. Records PDF and manual page numbers.
8. Produces JSON and CSV for later embedding.
"""

import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = ROOT / "upload"

OUTPUT_JSON = (
    UPLOAD_DIR
    / "maintenance_investigator_troubleshooting_chunks.json"
)

OUTPUT_CSV = (
    UPLOAD_DIR
    / "maintenance_investigator_troubleshooting_chunks.csv"
)


# ---------------------------------------------------------------------
# Source manuals
# ---------------------------------------------------------------------

MANUALS = [
    {
        "path": UPLOAD_DIR
        / "english---vf-series-service-manual---2001.pdf",
        "document_id": "96-8100-rev-c-2001",
        "manual_number": "96-8100",
        "title": "VF Series Service Manual",
        "revision": "Rev C",
        "publication_date": "June 2001",
        "source_role": "revision_reference",
    },
    {
        "path": UPLOAD_DIR
        / "english---vf-series-service-manual---2002.pdf",
        "document_id": "96-8100-rev-e-2002",
        "manual_number": "96-8100",
        "title": "VF Series Service Manual",
        "revision": "Rev E",
        "publication_date": "June 2002",
        "source_role": "primary",
    },
]


# ---------------------------------------------------------------------
# Diagnostic topics
# ---------------------------------------------------------------------

TOPICS = [
    {
        "name": "servo_following_errors",
        "subsystem": "axis_servo",
        "keywords": [
            "FOLLOWING ERROR",
            "SERVO ERROR TOO LARGE",
            "SERVO MOTOR VIBRATION",
            "SERVO MOTOR OVERHEATING",
            "SERVO OVERHEATING",
            "DRIVE FAULT",
            "OVERCURRENT",
            "MOTOR WIRING",
            "DRIVER CARD",
            "SERVO MOTOR",
            "ENCODER",
            "DC BUS",
        ],
    },
    {
        "name": "lead_screw_backlash",
        "subsystem": "axis_mechanical",
        "keywords": [
            "BACKLASH",
            "LEAD SCREW",
            "BINDING",
            "MOTOR COUPLING",
            "THRUST BEARING",
        ],
    },
    {
        "name": "tool_changer",
        "subsystem": "tool_changer",
        "keywords": [
            "TOOL CHANGER",
            "SHUTTLE",
            "TURRET",
            "CAROUSEL",
            "TOOL CHANGE",
            "ATC",
            "AUX AXIS",
        ],
    },
    {
        "name": "spindle_orientation",
        "subsystem": "spindle",
        "keywords": [
            "SPINDLE ORIENTATION",
            "ORIENTATION PIN",
            "ORIENT",
            "SPINDLE DRIVE",
            "VECTOR DRIVE",
        ],
    },
    {
        "name": "spindle_gearbox",
        "subsystem": "spindle_gearbox",
        "keywords": [
            "HIGH GEAR",
            "LOW GEAR",
            "GEARBOX",
            "TRANSMISSION",
        ],
    },
    {
        "name": "regen_spindle_drive",
        "subsystem": "spindle_drive",
        "keywords": [
            "REGEN",
            "REGENERATIVE",
            "SPINDLE DRIVE",
            "OVERHEAT",
            "OVERCURRENT",
            "INPUT LINE VOLTAGE",
        ],
    },
    {
        "name": "air_lubrication",
        "subsystem": "pneumatic_lubrication",
        "keywords": [
            "LOW AIR",
            "AIR PRESSURE",
            "LUBRICATION",
            "LOW LUBE",
            "LUBE",
            "COUNTERBALANCE",
            "HYDRAULIC",
        ],
    },
    {
        "name": "control_electronics",
        "subsystem": "control_electronics",
        "keywords": [
            "MOCON",
            "COMMUNICATION",
            "PROCESSOR",
            "IOPCB",
            "I/O PCB",
            "DRIVER PCB",
            "ELECTRICAL SERVICE",
            "POWER SUPPLY",
        ],
    },
]


# ---------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------

def extract_pdf_pages(pdf_path: Path) -> List[str]:
    """
    Extract PDF text one page at a time using pypdf.

    Returns:
        List where index 0 corresponds to PDF page 1.
    """

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "pypdf is not installed.\n"
            "Install it with:\n"
            "    pip install pypdf"
        ) from exc

    reader = PdfReader(str(pdf_path))

    pages: List[str] = []

    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            raise RuntimeError(
                f"Failed to extract PDF page "
                f"{page_number} from {pdf_path}: {exc}"
            ) from exc

        pages.append(text)

    return pages


# ---------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------

def normalize_pdf_text(text: str) -> str:
    """
    Normalize whitespace produced by PDF extraction.

    Important:
    We do not rewrite substantive words.
    This is only whitespace normalization.
    """

    text = text.replace("\x00", "")
    text = text.replace("\xa0", " ")
    text = text.replace("\r", "\n")

    # Collapse horizontal whitespace.
    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    # Collapse excessive blank lines.
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def clean_lines(text: str) -> List[str]:
    """
    Convert extracted page text into normalized non-empty lines.
    """

    text = normalize_pdf_text(text)

    lines: List[str] = []

    for raw in text.splitlines():
        line = raw.strip()

        if not line:
            continue

        line = re.sub(
            r"[ \t]+",
            " ",
            line,
        )

        lines.append(line)

    return lines


# ---------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------

def flattened_page_text(text: str) -> str:
    """
    Convert a PDF page to a single searchable line.

    This allows us to detect:

        1. TROUBLESHOOTING

    even if pypdf extracted:

        1.
        TROUBLESHOOTING
    """

    return re.sub(
        r"\s+",
        " ",
        normalize_pdf_text(text),
    ).strip()


def find_section_pages(
    pages: List[str],
    section_number: str,
    section_title: str,
    search_limit: int = 120,
) -> Tuple[int, int]:
    """
    Find the PDF page range containing a manual section.

    Returns:
        (zero_based_start_page, zero_based_end_page)

    end_page is exclusive.
    """

    title = re.escape(
        section_title.upper()
    )

    number = re.escape(
        section_number
    )

    start_pattern = re.compile(
        rf"\b{number}\s*\.\s*{title}\b",
        re.IGNORECASE,
    )

    start_page: Optional[int] = None

    # -------------------------------------------------------------
    # First pass: exact section number + title.
    # -------------------------------------------------------------

    for index, raw_page in enumerate(
        pages[:search_limit]
    ):
        flat = flattened_page_text(
            raw_page
        )

        if start_pattern.search(flat):
            start_page = index
            break

    # -------------------------------------------------------------
    # Fallback: title alone.
    # -------------------------------------------------------------

    if start_page is None:
        title_pattern = re.compile(
            rf"\b{title}\b",
            re.IGNORECASE,
        )

        for index, raw_page in enumerate(
            pages[:search_limit]
        ):
            flat = flattened_page_text(
                raw_page
            )

            if title_pattern.search(flat):
                start_page = index
                break

    if start_page is None:
        raise RuntimeError(
            f"Could not locate Section "
            f"{section_number} {section_title}"
        )

    # -------------------------------------------------------------
    # Locate next major section.
    # -------------------------------------------------------------

    next_section_pattern = re.compile(
        r"\b2\s*\.\s*ALARMS\b",
        re.IGNORECASE,
    )

    end_page = len(pages)

    for index in range(
        start_page + 1,
        len(pages),
    ):
        flat = flattened_page_text(
            pages[index]
        )

        if next_section_pattern.search(flat):
            end_page = index
            break

    return (
        start_page,
        end_page,
    )


# ---------------------------------------------------------------------
# Manual page detection
# ---------------------------------------------------------------------

def detect_manual_page(
    page_text: str,
) -> Optional[int]:
    """
    Attempt to identify the printed/manual page number.

    PDF page number and manual page number are intentionally
    stored separately.

    This function is conservative because body text can also
    contain standalone numbers.
    """

    lines = clean_lines(
        page_text
    )

    candidates: List[int] = []

    for line in lines:

        # Example:
        # 23
        if re.fullmatch(
            r"\d{1,3}",
            line,
        ):
            number = int(line)

            if 1 <= number <= 400:
                candidates.append(
                    number
                )

        # Example:
        # 23 TROUBLESHOOTING
        m = re.match(
            r"^(\d{1,3})\s+"
            r"(?:TROUBLESHOOTING|ALARMS)$",
            line,
            re.IGNORECASE,
        )

        if m:
            candidates.append(
                int(m.group(1))
            )

    if not candidates:
        return None

    # Prefer the first candidate.
    return candidates[0]


# ---------------------------------------------------------------------
# Header/footer filtering
# ---------------------------------------------------------------------

def is_repeated_header_or_footer(
    line: str,
) -> bool:

    normalized = re.sub(
        r"\s+",
        " ",
        line.strip().upper(),
    )

    repeated = {
        "TROUBLESHOOTING",
        "96-8100 REV C",
        "96-8100 REV E",
        "JUNE 2001",
        "JUNE 2002",
        "VF SERIES SERVICE MANUAL",
    }

    return normalized in repeated


# ---------------------------------------------------------------------
# Heading detection
# ---------------------------------------------------------------------

def is_heading(
    line: str,
) -> bool:
    """
    Detect likely troubleshooting headings.

    This is deliberately conservative.
    """

    line = line.strip()

    if len(line) < 3:
        return False

    if len(line) > 100:
        return False

    if is_repeated_header_or_footer(
        line
    ):
        return False

    upper = line.upper()

    # -------------------------------------------------------------
    # Strong heading: mostly uppercase.
    # -------------------------------------------------------------

    if re.fullmatch(
        r"[A-Z0-9][A-Z0-9 /&().,'_+\-:]{2,98}",
        line,
    ):
        return True

    # -------------------------------------------------------------
    # Numbered troubleshooting heading.
    #
    # Examples:
    #   1. SERVO MOTOR VIBRATION
    #   2. BACKLASH
    # -------------------------------------------------------------

    if re.match(
        r"^\d+(?:\.\d+)*[\s.)-]+[A-Za-z]",
        line,
    ):
        return True

    return False


# ---------------------------------------------------------------------
# Topic matching
# ---------------------------------------------------------------------

def topic_matches(
    text: str,
) -> List[Dict]:

    upper = text.upper()

    matches: List[Dict] = []

    for topic in TOPICS:

        hits = [
            keyword
            for keyword in topic["keywords"]
            if keyword in upper
        ]

        if hits:
            matches.append(
                {
                    "topic": topic["name"],
                    "subsystem": topic["subsystem"],
                    "matched_keywords": hits,
                }
            )

    return matches


# ---------------------------------------------------------------------
# Chunk extraction
# ---------------------------------------------------------------------

def extract_relevant_chunks(
    pages: List[str],
    manual: Dict,
) -> List[Dict]:
    """
    Extract relevant troubleshooting chunks from Section 1.
    """

    # -------------------------------------------------------------
    # Locate Section 1.
    # -------------------------------------------------------------

    section_start, section_end = find_section_pages(
        pages=pages,
        section_number="1",
        section_title="TROUBLESHOOTING",
    )

    print(
        "  Section 1 TROUBLESHOOTING: "
        f"PDF pages {section_start + 1}-"
        f"{section_end}"
    )

    # -------------------------------------------------------------
    # Diagnostic output.
    # -------------------------------------------------------------

    print(
        "  Section start preview:"
    )

    preview = flattened_page_text(
        pages[section_start]
    )

    print(
        "    "
        + preview[:500]
    )

    # -------------------------------------------------------------
    # Build section page list.
    # -------------------------------------------------------------

    section_pages: List[
        Tuple[int, str]
    ] = []

    for pdf_index in range(
        section_start,
        section_end,
    ):
        section_pages.append(
            (
                pdf_index + 1,
                pages[pdf_index],
            )
        )

    # -------------------------------------------------------------
    # Chunk state.
    # -------------------------------------------------------------

    chunks: List[Dict] = []

    current_lines: List[str] = []

    current_pdf_start: Optional[int] = None
    current_pdf_end: Optional[int] = None

    current_manual_pages: List[int] = []

    # -------------------------------------------------------------
    # Flush current chunk.
    # -------------------------------------------------------------

    def flush():
        nonlocal current_lines
        nonlocal current_pdf_start
        nonlocal current_pdf_end
        nonlocal current_manual_pages

        if not current_lines:
            return

        text = "\n".join(
            current_lines
        ).strip()

        text = normalize_pdf_text(
            text
        )

        # Ignore extremely small chunks.
        if len(text) < 120:

            current_lines = []
            current_pdf_start = None
            current_pdf_end = None
            current_manual_pages = []

            return

        matches = topic_matches(
            text
        )

        if matches:

            primary = matches[0]

            chunk = {
                "document_id": manual[
                    "document_id"
                ],

                "manual_number": manual[
                    "manual_number"
                ],

                "title": manual[
                    "title"
                ],

                "revision": manual[
                    "revision"
                ],

                "publication_date": manual[
                    "publication_date"
                ],

                "source_role": manual[
                    "source_role"
                ],

                "machine_family": "Haas VF Series",

                "section_number": "1",

                "section_title": "TROUBLESHOOTING",

                "chunk_type": "troubleshooting",

                "topic": primary[
                    "topic"
                ],

                "subsystem": primary[
                    "subsystem"
                ],

                "matched_topics": [
                    match["topic"]
                    for match in matches
                ],

                "matched_keywords": sorted(
                    {
                        keyword
                        for match in matches
                        for keyword
                        in match[
                            "matched_keywords"
                        ]
                    }
                ),

                "manual_page_start": (
                    min(
                        current_manual_pages
                    )
                    if current_manual_pages
                    else None
                ),

                "manual_page_end": (
                    max(
                        current_manual_pages
                    )
                    if current_manual_pages
                    else None
                ),

                "pdf_page_start": (
                    current_pdf_start
                ),

                "pdf_page_end": (
                    current_pdf_end
                ),

                "text": text,

                "text_length": len(
                    text
                ),

                "extraction_quality":
                    "source_pdf_text",

                "has_table": False,

                "has_diagram": False,
            }

            chunks.append(
                chunk
            )

        # Reset state.
        current_lines = []
        current_pdf_start = None
        current_pdf_end = None
        current_manual_pages = []

    # -------------------------------------------------------------
    # Process pages.
    # -------------------------------------------------------------

    for pdf_index, page in section_pages:

        manual_page = detect_manual_page(
            page
        )

        lines = clean_lines(
            page
        )

        filtered_lines: List[str] = []

        for line in lines:

            if is_repeated_header_or_footer(
                line
            ):
                continue

            # Remove standalone manual page number.
            if (
                manual_page is not None
                and line == str(manual_page)
            ):
                continue

            filtered_lines.append(
                line
            )

        # ---------------------------------------------------------
        # Process lines.
        # ---------------------------------------------------------

        for line in filtered_lines:

            # New heading = close previous chunk.
            if (
                is_heading(line)
                and current_lines
            ):
                flush()

            if current_pdf_start is None:
                current_pdf_start = pdf_index

            current_pdf_end = pdf_index

            if manual_page is not None:
                current_manual_pages.append(
                    manual_page
                )

            current_lines.append(
                line
            )

    # Flush final chunk.
    flush()

    return chunks


# ---------------------------------------------------------------------
# Chunk IDs
# ---------------------------------------------------------------------

def make_chunk_ids(
    chunks: List[Dict],
) -> None:

    counters: Dict[str, int] = {}

    for chunk in chunks:

        base = (
            f"{chunk['document_id']}"
            f"_{chunk['topic']}"
        )

        counters[base] = (
            counters.get(
                base,
                0,
            )
            + 1
        )

        chunk["chunk_id"] = (
            f"{base}_"
            f"{counters[base]:02d}"
        )


# ---------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------

def write_outputs(
    chunks: List[Dict],
) -> None:

    OUTPUT_JSON.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "dataset":
            "maintenance_investigator_troubleshooting",

        "description": (
            "Source-derived troubleshooting "
            "chunks from Haas VF Series "
            "Service Manual 96-8100 "
            "Rev C June 2001 and Rev E June 2002."
        ),

        "chunk_count":
            len(chunks),

        "chunks":
            chunks,
    }

    OUTPUT_JSON.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    fields = [
        "chunk_id",
        "document_id",
        "manual_number",
        "title",
        "revision",
        "publication_date",
        "source_role",
        "machine_family",
        "section_number",
        "section_title",
        "chunk_type",
        "topic",
        "subsystem",
        "matched_topics",
        "matched_keywords",
        "manual_page_start",
        "manual_page_end",
        "pdf_page_start",
        "pdf_page_end",
        "text_length",
        "extraction_quality",
        "has_table",
        "has_diagram",
        "text",
    ]

    with OUTPUT_CSV.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields,
        )

        writer.writeheader()

        for chunk in chunks:

            row = dict(
                chunk
            )

            row["matched_topics"] = (
                ";".join(
                    row["matched_topics"]
                )
            )

            row["matched_keywords"] = (
                ";".join(
                    row["matched_keywords"]
                )
            )

            writer.writerow(
                row
            )


# ---------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------

def print_summary(
    chunks: List[Dict],
) -> None:

    print()
    print("=" * 70)
    print(
        "TROUBLESHOOTING EXTRACTION SUMMARY"
    )
    print("=" * 70)

    print(
        f"Total chunks: {len(chunks)}"
    )

    by_revision: Dict[str, int] = {}

    by_topic: Dict[str, int] = {}

    for chunk in chunks:

        revision = chunk[
            "revision"
        ]

        topic = chunk[
            "topic"
        ]

        by_revision[
            revision
        ] = by_revision.get(
            revision,
            0,
        ) + 1

        by_topic[
            topic
        ] = by_topic.get(
            topic,
            0,
        ) + 1

    print()
    print("By revision:")

    for revision, count in sorted(
        by_revision.items()
    ):
        print(
            f"  {revision}: {count}"
        )

    print()
    print("By topic:")

    for topic, count in sorted(
        by_topic.items()
    ):
        print(
            f"  {topic}: {count}"
        )

    print()
    print(
        f"JSON: {OUTPUT_JSON}"
    )

    print(
        f"CSV:  {OUTPUT_CSV}"
    )

    print("=" * 70)


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():

    print()
    print(
        "Maintenance Investigator"
    )

    print(
        "Haas VF Series "
        "Troubleshooting Chunk Extractor"
    )

    print()

    all_chunks: List[Dict] = []

    for manual in MANUALS:

        print(
            "-" * 70
        )

        print(
            f"Extracting: "
            f"{manual['revision']} "
            f"{manual['publication_date']}"
        )

        print(
            f"File: {manual['path']}"
        )

        print()

        if not manual[
            "path"
        ].exists():

            raise SystemExit(
                "Missing manual:\n"
                f"  {manual['path']}"
            )

        # ---------------------------------------------------------
        # Extract PDF.
        # ---------------------------------------------------------

        pages = extract_pdf_pages(
            manual["path"]
        )

        print(
            f"  PDF pages extracted: "
            f"{len(pages)}"
        )

        # ---------------------------------------------------------
        # Extract troubleshooting.
        # ---------------------------------------------------------

        chunks = extract_relevant_chunks(
            pages=pages,
            manual=manual,
        )

        make_chunk_ids(
            chunks
        )

        print()
        print(
            "  Relevant troubleshooting "
            f"chunks: {len(chunks)}"
        )

        # ---------------------------------------------------------
        # Print chunks.
        # ---------------------------------------------------------

        for chunk in chunks:

            print(
                "    "
                f"{chunk['chunk_id']} | "
                f"{chunk['topic']} | "
                f"{chunk['subsystem']} | "
                f"manual pp. "
                f"{chunk['manual_page_start']}-"
                f"{chunk['manual_page_end']} | "
                f"PDF pp. "
                f"{chunk['pdf_page_start']}-"
                f"{chunk['pdf_page_end']}"
            )

        all_chunks.extend(
            chunks
        )

        print()

    # -----------------------------------------------------------------
    # Write output.
    # -----------------------------------------------------------------

    write_outputs(
        all_chunks
    )

    print_summary(
        all_chunks
    )


if __name__ == "__main__":
    main()