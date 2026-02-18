"""Document parsing for SEC filings."""

import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
from bs4 import BeautifulSoup

from app.models.document import ParsedDocument

logger = logging.getLogger(__name__)


class DocumentParser:
    """Parse SEC filings from various formats (PDF, HTML, TXT)."""

    # Ordered section headers for 10-K filings.
    # Order matters — each section ends where the next one begins.
    SECTION_HEADERS = [
        ("item_1", r"ITEM\s+1\.?\s+BUSINESS"),
        ("item_1a", r"ITEM\s+1A\.?\s+RISK\s+FACTORS"),
        ("item_1b", r"ITEM\s+1B\.?\s+UNRESOLVED"),
        ("item_1c", r"ITEM\s+1C\.?\s+CYBERSECURITY"),
        ("item_2", r"ITEM\s+2\.?\s+PROPERTIES"),
        ("item_3", r"ITEM\s+3\.?\s+LEGAL"),
        ("item_4", r"ITEM\s+4\.?\s+MINE"),
        ("item_5", r"ITEM\s+5\.?\s+MARKET"),
        ("item_6", r"ITEM\s+6\.?\s+(?:RESERVED|\[RESERVED\])"),
        ("item_7", r"ITEM\s+7\.?\s+MANAGEMENT"),
        ("item_7a", r"ITEM\s+7A\.?\s+QUANTITATIVE"),
        ("item_8", r"ITEM\s+8\.?\s+FINANCIAL\s+STATEMENTS"),
        ("item_9", r"ITEM\s+9\.?\s+CHANGES"),
    ]

    # Sections relevant for AI readiness scoring
    TARGET_SECTIONS = {"item_1", "item_1a", "item_7", "item_7a"}

    def parse_filing(self, file_path: Path, ticker: str) -> ParsedDocument:
        """
        Parse a SEC filing and extract structured content.

        Args:
            file_path: Path to the filing document
            ticker: Company ticker symbol

        Returns:
            ParsedDocument with extracted content and metadata
        """
        suffix = file_path.suffix.lower()

        # Parse based on file type
        if suffix == ".pdf":
            content = self._parse_pdf(file_path)
        elif suffix in [".htm", ".html", ".txt"]:
            content = self._parse_html(file_path)
        else:
            # Try HTML parsing as default for unknown types
            content = self._parse_html(file_path)

        # Extract sections
        sections = self._extract_sections(content)

        # Generate content hash for deduplication
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Extract filing metadata from path
        filing_type, filing_date = self._extract_metadata(file_path)

        return ParsedDocument(
            company_ticker=ticker,
            filing_type=filing_type,
            filing_date=filing_date,
            content=content,
            sections=sections,
            source_path=str(file_path),
            content_hash=content_hash,
            word_count=len(content.split()),
        )

    def _parse_pdf(self, file_path: Path) -> str:
        """Extract text from PDF using pdfplumber."""
        text_parts = []

        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
        except Exception as e:
            logger.error(f"Error parsing PDF {file_path}: {e}")
            raise

        return "\n\n".join(text_parts)

    def _parse_html(self, file_path: Path) -> str:
        """Extract text from HTML/TXT filing."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Check if it's SEC SGML format (contains <DOCUMENT> tags)
            if "<DOCUMENT>" in content and "<TYPE>" in content:
                logger.info(f"Detected SEC SGML format in {file_path}")
                return self._parse_sec_sgml(content)

            soup = BeautifulSoup(content, "lxml")

            # Remove script and style elements
            for element in soup(["script", "style"]):
                element.decompose()

            # Get text
            text = soup.get_text(separator="\n")

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            text = "\n".join(line for line in lines if line)

            return text

        except Exception as e:
            logger.error(f"Error parsing HTML {file_path}: {e}")
            raise

    def _extract_sections(self, content: str) -> dict[str, str]:
        """
        Extract key sections from 10-K content.

        Strategy: find the LAST occurrence of each section header to skip
        Table of Contents references, then use the next section header as
        the end boundary.
        """
        content_upper = content.upper()

        # Find the last (i.e. actual body) occurrence of each section header
        header_positions = []  # list of (position, section_name)
        for section_name, pattern in self.SECTION_HEADERS:
            # Find all matches — take the last one to skip ToC references
            matches = list(re.finditer(pattern, content_upper))
            if matches:
                last_match = matches[-1]
                header_positions.append((last_match.start(), section_name))

        # Sort by position in the document
        header_positions.sort(key=lambda x: x[0])

        # Extract sections: each section runs from its header to the next header
        sections = {}
        for i, (start, section_name) in enumerate(header_positions):
            if section_name not in self.TARGET_SECTIONS:
                continue

            # End at the next section header, or end of document
            if i + 1 < len(header_positions):
                end = header_positions[i + 1][0]
            else:
                end = len(content)

            section_text = content[start:end].strip()
            if section_text:
                sections[section_name] = section_text

        return sections

    def _extract_metadata(self, file_path: Path) -> tuple[str, datetime]:
        """Extract filing type and date from file path."""
        parts = file_path.parts

        # Try to find filing type from path
        # Path structure: .../ticker/filing_type/accession/file
        # Library writes DEF-14A as DEFA14A (no hyphen) in path
        filing_type = "UNKNOWN"
        for part in parts:
            if part == "DEFA14A":
                filing_type = "DEF-14A"
                break
            if part in ["10-K", "10-Q", "8-K", "DEF-14A"]:
                filing_type = part
                break

        # Try to extract date from accession number (format: 0000000000-YY-NNNNNN)
        filing_date = datetime.now(timezone.utc)
        for part in parts:
            date_match = re.search(r"-(\d{2})-", part)
            if date_match:
                year = int(date_match.group(1))
                year = 2000 + year if year < 50 else 1900 + year
                filing_date = datetime(year, 1, 1, tzinfo=timezone.utc)
                break

        return filing_type, filing_date

    def _parse_sec_sgml(self, content: str) -> str:
        """Parse SEC SGML format filing (full-submission.txt)."""
        # Extract only the main document content, skip headers
        documents = []

        # Split into document sections
        doc_pattern = r"<DOCUMENT>(.*?)</DOCUMENT>"
        doc_matches = re.findall(doc_pattern, content, re.DOTALL)

        for doc_content in doc_matches:
            # Check document type - we want the main filing, not exhibits
            type_match = re.search(r"<TYPE>(.*?)\n", doc_content)
            if not type_match:
                continue

            doc_type = type_match.group(1).strip()

            # Skip non-main documents (exhibits, graphics, etc.)
            if any(
                skip in doc_type for skip in ["EX-", "GRAPHIC", "XML", "ZIP", "EXCEL", "JSON"]
            ):
                continue

            # Extract the text portion (after <TEXT> tag)
            text_match = re.search(r"<TEXT>(.*?)</TEXT>", doc_content, re.DOTALL)
            if not text_match:
                continue

            text_content = text_match.group(1)

            # Skip binary/encoded content (uuencoded PDFs, base64, etc.)
            # These appear as duplicate filing entries embedded as PDF
            stripped = text_content.lstrip()
            if (
                stripped.startswith("<PDF>")       # SEC PDF wrapper tag
                or stripped.startswith("begin 6")  # uuencode header (begin 644 ...)
                or stripped.startswith("%PDF")      # raw PDF content
            ):
                logger.debug(f"Skipping binary/encoded document: {doc_type}")
                continue

            # Parse HTML within the TEXT section
            soup = BeautifulSoup(text_content, "html.parser")

            # Remove unwanted elements
            for element in soup(
                [
                    "script",
                    "style",
                    "ix:hidden",
                    "ix:nonfraction",
                    "ix:nonnumeric",  # XBRL inline elements
                    "table",  # Tables often contain layout/formatting, not content
                ]
            ):
                element.decompose()

            # Get clean text
            text = soup.get_text(separator="\n")

            # Clean up common SEC artifacts
            text = self._clean_sec_text(text)

            documents.append(text)

        # Join all main documents
        return "\n\n".join(documents)

    def _clean_sec_text(self, text: str) -> str:
        """Clean up common SEC filing artifacts and formatting issues."""
        # Remove excessive whitespace while preserving paragraph breaks
        lines = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                # Remove multiple spaces
                line = re.sub(r"\s+", " ", line)
                lines.append(line)

        text = "\n".join(lines)

        # Remove common SEC artifacts
        text = re.sub(
            r"UNITED STATES\s+SECURITIES AND EXCHANGE COMMISSION.*?FORM \d+-[KQ]",
            "",
            text,
            flags=re.DOTALL,
        )
        text = re.sub(r"\*{3,}", "", text)  # Remove separator lines
        text = re.sub(r"-{3,}", "", text)
        text = re.sub(r"_{3,}", "", text)
        text = re.sub(r"={3,}", "", text)

        # Remove page numbers and headers (common patterns)
        text = re.sub(r"\n\d+\n", "\n", text)
        text = re.sub(r"Table of Contents", "", text, flags=re.IGNORECASE)

        # Remove extra blank lines (keep max 2 consecutive newlines)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()
