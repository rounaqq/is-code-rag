"""
Pydantic v2 Data Schema for Structural IS Code Clause Chunks.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ClauseChunk(BaseModel):
    code_id: str
    edition_year: int
    clause_number: str
    clause_title: str
    title_ocr_raw: Optional[str] = None
    page_number: List[int]
    raw_text: str
    cleaned_text: str
    cross_references: List[str] = Field(default_factory=list)
    applicable_components: List[str] = Field(default_factory=list)
    needs_manual_check: bool = True
    verified: bool = False
    verified_by: Optional[str] = None
    formula_verified: Optional[str] = None
    verified_text: Optional[str] = None

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
