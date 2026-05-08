"""
Hierarchical Document Chunking Module
Preserves legal document structure (Law → Article → Paragraph)
"""
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """Hierarchical document chunk with context"""
    content: str
    chunk_id: str
    
    # Hierarchy
    law_name: Optional[str] = None
    law_number: Optional[str] = None
    chapter: Optional[str] = None
    article_number: Optional[str] = None
    paragraph_number: Optional[str] = None
    
    # Context
    parent_context: Optional[str] = None  # Title of parent section
    full_hierarchy: Optional[str] = None  # Full path
    
    # Metadata
    chunk_type: str = "paragraph"  # "law", "chapter", "article", "paragraph"
    level: int = 0  # Hierarchy depth
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class HierarchicalChunker:
    """
    Chunks legal documents hierarchically
    - Preserves document structure
    - Maintains parent-child relationships
    - Enables precise citations
    """
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Patterns for legal document structure
        self.patterns = {
            "law": [
                r"(?:القانون|المرسوم|الأمر|القرار)\s+رقم\s+([\d\-\.]+)",
                r"(?:Law|Decree|Order)\s+(?:No\.|Number)\s+([\d\-\.]+)",
                r"(?:Loi|Décret|Arrêté)\s+(?:n°|numéro)\s+([\d\-\.]+)"
            ],
            "chapter": [
                r"(?:الباب|الفصل)\s+([الأول|الثاني|الثالث|الرابع|الخامس|\d+])",
                r"Chapter\s+(\d+|[IVX]+)",
                r"Chapitre\s+(\d+|[IVX]+)"
            ],
            "article": [
                r"المادة\s+(\d+)",
                r"Article\s+(\d+)",
                r"Article\s+(\d+)"
            ],
            "paragraph": [
                r"الفقرة\s+(\d+)",
                r"Paragraph\s+(\d+)",
                r"Paragraphe\s+(\d+)"
            ]
        }
        
        # Title patterns
        self.title_patterns = [
            r"(?:الباب|الفصل)\s+[الأول|الثاني|الثالث|الرابع|الخامس|\d+]\s*[:\-]\s*(.+?)(?:\n|$)",
            r"Chapter\s+\d+\s*[:\-]\s*(.+?)(?:\n|$)",
            r"Chapitre\s+\d+\s*[:\-]\s*(.+?)(?:\n|$)"
        ]
    
    def chunk_document(self, document: Dict) -> List[DocumentChunk]:
        """Chunk document hierarchically"""
        content = document.get("content", "")
        metadata = document.get("metadata", {})
        
        # Extract law information
        law_name, law_number = self._extract_law_info(content, metadata)
        
        # Split into sections
        sections = self._split_into_sections(content)
        
        # Process each section
        chunks = []
        for section in sections:
            section_chunks = self._process_section(
                section,
                law_name,
                law_number,
                metadata
            )
            chunks.extend(section_chunks)
        
        logger.info(f"Created {len(chunks)} hierarchical chunks from document")
        
        return chunks
    
    def _extract_law_info(self, content: str, metadata: Dict) -> Tuple[Optional[str], Optional[str]]:
        """Extract law name and number"""
        
        # Try metadata first
        law_name = metadata.get("law_name")
        law_number = metadata.get("law_number")
        
        if law_name and law_number:
            return law_name, law_number
        
        # Try extracting from content
        for pattern in self.patterns["law"]:
            match = re.search(pattern, content)
            if match:
                law_number = match.group(1)
                law_name = match.group(0)
                return law_name, law_number
        
        return None, None
    
    def _split_into_sections(self, content: str) -> List[Dict]:
        """Split content into hierarchical sections"""
        sections = []
        
        # Split by articles (most common structure)
        article_pattern = r"(المادة\s+\d+[^\n]*)"
        parts = re.split(article_pattern, content)
        
        current_chapter = None
        current_chapter_title = None
        
        for i in range(0, len(parts), 2):
            # Check for chapter before article
            if i > 0:
                prev_text = parts[i-1] if i > 0 else ""
                chapter_match = None
                for pattern in self.patterns["chapter"]:
                    chapter_match = re.search(pattern, prev_text)
                    if chapter_match:
                        current_chapter = chapter_match.group(1)
                        # Try to extract chapter title
                        for title_pattern in self.title_patterns:
                            title_match = re.search(title_pattern, prev_text)
                            if title_match:
                                current_chapter_title = title_match.group(1).strip()
                                break
                        break
            
            # Get article header and content
            article_header = parts[i] if i < len(parts) else ""
            article_content = parts[i+1] if i+1 < len(parts) else ""
            
            if article_header or article_content:
                # Extract article number
                article_number = None
                for pattern in self.patterns["article"]:
                    match = re.search(pattern, article_header)
                    if match:
                        article_number = match.group(1)
                        break
                
                sections.append({
                    "chapter": current_chapter,
                    "chapter_title": current_chapter_title,
                    "article_number": article_number,
                    "article_header": article_header,
                    "content": article_content.strip()
                })
        
        return sections
    
    def _process_section(
        self,
        section: Dict,
        law_name: Optional[str],
        law_number: Optional[str],
        metadata: Dict
    ) -> List[DocumentChunk]:
        """Process a section into chunks"""
        chunks = []
        
        content = section.get("content", "")
        article_number = section.get("article_number")
        chapter = section.get("chapter")
        chapter_title = section.get("chapter_title")
        
        # Build parent context
        parent_context_parts = []
        if chapter_title:
            parent_context_parts.append(chapter_title)
        if chapter:
            parent_context_parts.append(f"الباب {chapter}")
        parent_context = " - ".join(parent_context_parts) if parent_context_parts else None
        
        # Build full hierarchy
        hierarchy_parts = []
        if law_name:
            hierarchy_parts.append(law_name)
        if chapter:
            hierarchy_parts.append(f"الباب {chapter}")
        if article_number:
            hierarchy_parts.append(f"المادة {article_number}")
        full_hierarchy = " > ".join(hierarchy_parts)
        
        # Split content into paragraphs if too long
        if len(content) > self.chunk_size:
            paragraphs = self._split_into_paragraphs(content)
            
            for i, para in enumerate(paragraphs, 1):
                chunk_id = f"{law_number or 'unknown'}_{article_number or 'unknown'}_{i}"
                
                chunk = DocumentChunk(
                    content=para,
                    chunk_id=chunk_id,
                    law_name=law_name,
                    law_number=law_number,
                    chapter=chapter,
                    article_number=article_number,
                    paragraph_number=str(i),
                    parent_context=parent_context,
                    full_hierarchy=full_hierarchy,
                    chunk_type="paragraph",
                    level=3,
                    metadata=metadata
                )
                chunks.append(chunk)
        else:
            # Single chunk for article
            chunk_id = f"{law_number or 'unknown'}_{article_number or 'unknown'}"
            
            chunk = DocumentChunk(
                content=content,
                chunk_id=chunk_id,
                law_name=law_name,
                law_number=law_number,
                chapter=chapter,
                article_number=article_number,
                parent_context=parent_context,
                full_hierarchy=full_hierarchy,
                chunk_type="article",
                level=2,
                metadata=metadata
            )
            chunks.append(chunk)
        
        return chunks
    
    def _split_into_paragraphs(self, content: str) -> List[str]:
        """Split content into paragraphs with overlap"""
        # Split by newlines or sentence boundaries
        sentences = re.split(r'[.。]\s+', content)
        
        paragraphs = []
        current_para = []
        current_length = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_length = len(sentence)
            
            if current_length + sentence_length > self.chunk_size and current_para:
                # Save current paragraph
                paragraphs.append(". ".join(current_para) + ".")
                
                # Start new paragraph with overlap
                overlap_sentences = current_para[-2:] if len(current_para) >= 2 else current_para
                current_para = overlap_sentences + [sentence]
                current_length = sum(len(s) for s in current_para)
            else:
                current_para.append(sentence)
                current_length += sentence_length
        
        # Add last paragraph
        if current_para:
            paragraphs.append(". ".join(current_para) + ".")
        
        return paragraphs
    
    def get_full_article(self, chunks: List[DocumentChunk], article_number: str) -> Optional[str]:
        """Reconstruct full article from chunks"""
        article_chunks = [
            c for c in chunks
            if c.article_number == article_number
        ]
        
        if not article_chunks:
            return None
        
        # Sort by paragraph number
        article_chunks.sort(key=lambda c: int(c.paragraph_number or 0))
        
        # Combine content
        full_content = "\n\n".join(c.content for c in article_chunks)
        
        return full_content
    
    def build_citation(self, chunk: DocumentChunk) -> str:
        """Build precise citation from chunk"""
        citation_parts = []
        
        if chunk.law_name:
            citation_parts.append(chunk.law_name)
        
        if chunk.article_number:
            citation_parts.append(f"المادة {chunk.article_number}")
        
        if chunk.paragraph_number:
            citation_parts.append(f"الفقرة {chunk.paragraph_number}")
        
        return "، ".join(citation_parts)
    
    def to_dict(self, chunk: DocumentChunk) -> Dict:
        """Convert chunk to dictionary for storage"""
        return {
            "content": chunk.content,
            "chunk_id": chunk.chunk_id,
            "law_name": chunk.law_name,
            "law_number": chunk.law_number,
            "chapter": chunk.chapter,
            "article_number": chunk.article_number,
            "paragraph_number": chunk.paragraph_number,
            "parent_context": chunk.parent_context,
            "full_hierarchy": chunk.full_hierarchy,
            "chunk_type": chunk.chunk_type,
            "level": chunk.level,
            "metadata": chunk.metadata
        }
