"""Extract text from various file formats"""
import os
from pathlib import Path
from typing import Optional, Tuple
import app.config as config
from app.logger import logger

class FileParser:
    """Parse different file types and extract text"""
    
    @staticmethod
    def parse(file_path: str) -> Optional[str]:
        """Extract text from file"""
        try:
            ext = Path(file_path).suffix.lower()
            
            if ext == ".txt" or ext == ".md":
                return FileParser._parse_text(file_path)
            elif ext == ".pdf":
                return FileParser._parse_pdf(file_path)
            elif ext == ".docx" or ext == ".doc":
                return FileParser._parse_docx(file_path)
            elif ext == ".json":
                return FileParser._parse_json(file_path)
            elif ext == ".csv":
                return FileParser._parse_csv(file_path)
            elif ext in [".py", ".js"]:
                return FileParser._parse_code(file_path)
            elif ext in [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"]:
                return FileParser._parse_video_metadata(file_path)
            elif ext in [".pptx", ".ppt"]:
                return FileParser._parse_pptx(file_path)
            else:
                return None
        except Exception as e:
            logger.warning(f"Error parsing {file_path}: {e}")
            return None
    
    @staticmethod
    def _parse_text(file_path: str) -> str:
        """Parse .txt or .md files"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()[:5000]  # Limit to 5000 chars
    
    @staticmethod
    def _parse_pdf(file_path: str) -> Optional[str]:
        """Parse PDF files"""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            text = ""
            for page in doc[:5]:  # First 5 pages
                text += page.get_text()
            return text[:5000]
        except Exception as e:
            logger.debug(f"PDF parse error: {e}")
            return None
    
    @staticmethod
    def _parse_docx(file_path: str) -> Optional[str]:
        """Parse .docx files"""
        try:
            from docx import Document
            doc = Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
            return text[:5000]
        except Exception as e:
            logger.debug(f"DOCX parse error: {e}")
            return None
    
    @staticmethod
    def _parse_json(file_path: str) -> str:
        """Parse JSON files"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()[:5000]
            
    @staticmethod
    def _parse_pptx(file_path: str) -> Optional[str]:
        """Parse .pptx files"""
        try:
            from pptx import Presentation
            prs = Presentation(file_path)
            text = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text.append(shape.text)
            return "\n".join(text)[:5000]
        except Exception as e:
            logger.debug(f"PPTX parse error: {e}")
            return None
    
    @staticmethod
    def _parse_csv(file_path: str) -> str:
        """Parse CSV files"""
        import csv
        text = ""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    if i >= 50:  # First 50 rows
                        break
                    text += " ".join(row) + "\n"
            return text[:5000]
        except Exception as e:
            logger.debug(f"CSV parse error: {e}")
            return FileParser._parse_text(file_path)
    
    @staticmethod
    def _parse_code(file_path: str) -> str:
        """Parse code files"""
        return FileParser._parse_text(file_path)
        
    @staticmethod
    def _parse_video_metadata(file_path: str) -> str:
        """Parse video files based on filename metadata"""
        name = os.path.basename(file_path)
        name_clean = name.replace("_", " ").replace("-", " ").replace(".", " ")
        return f"Video file: {name_clean}"
    
    @staticmethod
    def get_file_metadata(file_path: str) -> dict:
        """Extract file metadata"""
        stat = os.stat(file_path)
        return {
            "path": file_path,
            "name": os.path.basename(file_path),
            "size": stat.st_size,
            "modified_time": stat.st_mtime,
            "created_time": stat.st_ctime,
            "extension": Path(file_path).suffix.lower(),
        }
