import os
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pypdf import PdfReader
from llama_cloud_services import LlamaParse
from dotenv import load_dotenv
import mimetypes
from openai import OpenAI

load_dotenv()

# System prompt defined outside of functions (decoupling)
SYSTEM_PROMPT = """You are a document analysis expert. Analyze the provided document content and categorize it.

Document Types:
- resume: Professional CV or resume documents
- letter: Formal letters, cover letters, business correspondence
- invoice: Bills, invoices, receipts, financial documents
- blog: Blog posts, articles, informal writing
- other: Any document that doesn't fit the above categories (reports, manuals, contracts, etc.)

Examples:
- A document with "Dear Hiring Manager" and work experience → resume
- A document with "Invoice #123" and amounts → invoice  
- A document with "Dear Sir/Madam" and formal tone → letter
- A document with casual writing and personal opinions → blog
- A technical manual or legal contract → other

Return your analysis in the exact JSON format requested."""

@dataclass
class DocumentInfo:
    """Response format class for OpenAI structured output"""
    doc_type: str  # resume, letter, invoice, blog, other
    lang_type: str  # detected language (en, es, fr, etc.)
    summary: str   # brief summary of the document content

class FileChecker:
    def check_file_exists(self, file_path: str) -> Dict[str, Any]:
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}
        return {"success": True}

class PDFPageChecker:
    def __init__(self, max_pages: int = 5):
        self.max_pages = max_pages
    
    def check_pages(self, file_path: str) -> Dict[str, Any]:
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type == "application/pdf":
            try:
                reader = PdfReader(file_path)
                page_count = len(reader.pages)
                print(f"📄 Document has {page_count} pages")
                if page_count > self.max_pages:
                    return {"error": f"Document too long (more than {self.max_pages} pages)"}
            except Exception as e:
                return {"error": f"Cannot read PDF: {str(e)}"}
        else:
            print(f"🖼️ Processing non-PDF file: {file_path}")
        
        return {"success": True}

class PDFSizeChecker:
    def __init__(self, max_size_mb: int = 10):
        self.max_size_mb = max_size_mb
    
    def check_size(self, file_path: str) -> Dict[str, Any]:
        try:
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)  # Convert to MB
            
            if file_size_mb > self.max_size_mb:
                return {"error": f"File too large: {file_size_mb:.2f}MB (max: {self.max_size_mb}MB)"}
            
            print(f"📁 File size: {file_size_mb:.2f}MB")
            return {"success": True}
        except Exception as e:
            return {"error": f"Cannot check file size: {str(e)}"}

class LlamaParseService:
    def parse_document(self, file_path: str, api_key: str) -> Dict[str, Any]:
        try:
            parser = LlamaParse(
                api_key=api_key,
                result_type="markdown",
                verbose=True,
                language="en"
            )
            
            result = parser.parse(file_path)
            
            # Fixed: Handle JobResult object properly
            if hasattr(result, 'text'):
                # If result has text attribute directly
                text = result.text
            elif isinstance(result, list) and len(result) > 0:
                # If result is a list of documents
                text = result[0].text if hasattr(result[0], 'text') else str(result[0])
            else:
                # Fallback: convert to string
                text = str(result)
            
            print(f"Extracted {len(text)} characters")
            return {"success": True, "text": text}
            
        except Exception as e:
            return {"error": f"LlamaParse failed: {str(e)}"}

class DocumentReader:
    def read_file_data(self, file_data: str) -> Dict[str, Any]:
        if not file_data or len(file_data.strip()) == 0:
            return {"error": "No content to read"}
        
        print(f"Reading {len(file_data)} characters of content")
        return {"success": True, "content": file_data}

class GitHubAI:
    
    def __init__(self, 
                 api_key: Optional[str] = None, 
                 base_url: str = "https://models.inference.ai.azure.com",
                 model: str = "gpt-4o-mini"):
        """
        Initialize GitHub AI
        
        Args:
            api_key: GitHub token or OpenAI API key
            base_url: GitHub Models endpoint (default) or OpenAI endpoint
            model: Model name (e.g., gpt-4o, gpt-4o-mini)
        """
        self.client = OpenAI(
            api_key=api_key or os.getenv("GITHUB_TOKEN") or os.getenv("OPENAI_API_KEY"),
            base_url=base_url
        )
        self.model = model
    
    def analyze_document(self, text: str) -> Dict[str, Any]:
        """
        Analyze document using OpenAI response format with structured output
        """
        try:
            # Truncate text to avoid token limits
            content = text[:4000] if len(text) > 4000 else text
            
            # Use OpenAI's structured output with response_format
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Analyze this document:\n\n{content}"}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "document_analysis",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "doc_type": {
                                    "type": "string",
                                    "enum": ["resume", "letter", "invoice", "blog", "other"]
                                },
                                "lang_type": {
                                    "type": "string",
                                    "description": "Detected language code (e.g., en, es, fr)"
                                },
                                "summary": {
                                    "type": "string",
                                    "description": "Brief summary of the document content"
                                }
                            },
                            "required": ["doc_type", "lang_type", "summary"],
                            "additionalProperties": False
                        }
                    }
                },
                temperature=0.1,
                max_tokens=500
            )
            
            # Parse the structured response
            analysis_json = json.loads(response.choices[0].message.content)
            
            # Create DocumentInfo object for type safety
            doc_info = DocumentInfo(
                doc_type=analysis_json["doc_type"],
                lang_type=analysis_json["lang_type"],
                summary=analysis_json["summary"]
            )
            
            return {
                "success": True, 
                "analysis": {
                    "doc_type": doc_info.doc_type,
                    "lang_type": doc_info.lang_type,
                    "summary": doc_info.summary
                },
                "token_usage": response.usage.total_tokens if response.usage else 0
            }
            
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse AI response as JSON: {str(e)}"}
        except Exception as e:
            return {"error": f"Document analysis failed: {str(e)}"}

class DocumentProcessor:
    """Main processor class that orchestrates the entire pipeline"""
    
    def __init__(self, 
                 max_pages: int = 10, 
                 max_size_mb: int = 10,
                 ai_model: str = "gpt-4o-mini"):
        # Initialize all components (dependency injection)
        self.file_checker = FileChecker()
        self.page_checker = PDFPageChecker(max_pages)
        self.size_checker = PDFSizeChecker(max_size_mb)
        self.parser = LlamaParseService()
        self.reader = DocumentReader()
        self.analyzer = GitHubAI(model=ai_model)
    
    def process(self, file_path: str) -> Dict[str, Any]:
        """Process document through the entire pipeline"""
        
        # Step 1: File validation
        result = self.file_checker.check_file_exists(file_path)
        if "error" in result:
            return result
        
        # Step 2: Size validation
        result = self.size_checker.check_size(file_path)
        if "error" in result:
            return result
        
        # Step 3: Page count validation (for PDFs)
        result = self.page_checker.check_pages(file_path)
        if "error" in result:
            return result
        
        # Step 4: Document parsing
        api_key = os.getenv("LLAMA_CLOUD_API_KEY")
        if not api_key:
            return {"error": "LLAMA_CLOUD_API_KEY not found in environment variables"}
        
        parse_result = self.parser.parse_document(file_path, api_key)
        if "error" in parse_result:
            return parse_result
        
        # Step 5: Content reading
        read_result = self.reader.read_file_data(parse_result["text"])
        if "error" in read_result:
            return read_result
        
        # Step 6: AI analysis
        analysis_result = self.analyzer.analyze_document(read_result["content"])
        if "error" in analysis_result:
            return analysis_result
        
        # Return comprehensive result
        return {
            "success": True,
            "file_path": file_path,
            "file_size_mb": round(os.path.getsize(file_path) / (1024 * 1024), 2),
            "content_length": len(read_result["content"]),
            "tokens_used": analysis_result.get("token_usage", 0),
            "analysis": analysis_result["analysis"]
        }

def main():
    """Main execution function"""
    # Configuration
    FILE_PATH = "C:/Users/karth/Vinoth/test_documents/Chekuri, Karthik - Resume (1) (1).docx"  # Change to your document path
    MAX_PAGES = 10
    MAX_SIZE_MB = 10
    AI_MODEL = "gpt-4o-mini"  
    
    # Initialize processor
    processor = DocumentProcessor(
        max_pages=MAX_PAGES,
        max_size_mb=MAX_SIZE_MB, 
        ai_model=AI_MODEL
    )
    
    # Process document
    print(f"🚀 Processing document: {FILE_PATH}")
    result = processor.process(FILE_PATH)
    
    # Output results
    print("\n" + "="*50)
    print("DOCUMENT ANALYSIS RESULTS")
    print("="*50)
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
