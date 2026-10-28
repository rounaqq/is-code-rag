"""
Pydantic v2 Data Schema for Structural IS Code Clause Chunks.

Step 4: Chunking & Metadata Enrichment.
Enforces clause/sub-clause granularity, separate table/figure chunk typing,
and complete metadata enrichment:
- IS code number
- Year / edition
- Amendment
- Section
- Clause number
- Title
- Applicability
- Keywords
- Dependencies
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ClauseChunk(BaseModel):
    """
    Standard clause chunk schema representing digitized Indian Standard provisions.
    Contains core text, hierarchy metadata, and verification attribution.
    """
    code_id: str
    edition_year: int
    clause_number: str
    clause_title: str
    title_ocr_raw: Optional[str] = None
    page_number: List[int] = Field(default_factory=list)
    raw_text: str = ""
    cleaned_text: str = ""
    cross_references: List[str] = Field(default_factory=list)
    applicable_components: List[str] = Field(default_factory=list)
    needs_manual_check: bool = True
    verified: bool = False
    verified_by: Optional[str] = None
    formula_verified: Optional[str] = None
    verified_text: Optional[str] = None

    # Step 4 enriched metadata fields
    amendment: Optional[str] = None
    section: Optional[str] = None
    applicability: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    chunk_type: str = "clause"  # "clause" | "table" | "figure" | "amendment" | "errata" | "example"

    @property
    def embedding_text(self) -> str:
        """
        Text prepared for embedding generation.
        Returns verified_text if present, otherwise cleaned_text.
        Never returns raw_text.
        """
        if self.verified_text is not None:
            return self.verified_text
        return self.cleaned_text


class EnrichedChunk(BaseModel):
    """
    Unified metadata-enriched structural chunk for the complete multi-standard corpus.
    Fulfills Step 4 requirements for document stores and hybrid vector indexing.
    """
    chunk_id: str
    code: str
    year: int = 2000
    amendment: Optional[str] = None
    section: Optional[str] = None
    clause_number: str
    title: str
    applicability: str = "Structural engineering design"
    keywords: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    chunk_type: str = "clause"  # "clause", "table", "figure", "amendment", "errata", "example"
    text: str
    cross_references: List[str] = Field(default_factory=list)
    equations: List[str] = Field(default_factory=list)
    verified: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
