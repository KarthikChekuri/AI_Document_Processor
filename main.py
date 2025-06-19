import os
import json
import requests
from pypdf import PdfReader
from llama_cloud_services import LlamaParse
from dotenv import load_dotenv

load_dotenv()

def process_document(file_path):
    """
    Main function that processes a document following the flow diagram:
    1. Check page limit (max 5 pages)
    2. Extract content using LlamaParse (handles images, tables, diagrams)
    3. Send to local LM Studio Qwen 2.5 model for analysis
    4. Return structured JSON output
    """
    
    # STEP 1: CHECK PAGE LIMIT (MAX 5 PAGES)
    # Read the PDF to count pages
    reader = PdfReader(file_path)
    page_count = len(reader.pages)
    print(f"📄 Document has {page_count} pages")
    
    # If more than 5 pages, reject the document
    if page_count > 7:
        return {"error": "Document too long (more than 5 pages)"}
    
    # STEP 2: EXTRACT CONTENT WITH LLAMAPARSE
    # LlamaParse can handle multimodal content (text, images, tables, diagrams)
    parser = LlamaParse(
        api_key=os.getenv("API_KEY"),  # Get API key from .env file
        result_type="markdown"  # Get content as markdown format
    )
    
    documents = parser.load_data(file_path)  # Parse the document
    text = documents[0].text  # Get the extracted text
    print(f"Extracted {len(text)} characters")
    
    # STEP 3: SEND TO LOCAL LM STUDIO FOR ANALYSIS
    # Create a prompt asking LLM to analyze the document
    prompt = f"""Analyze this document and return JSON:
    {{
        "language": "detect language",
        "document_type": "resume/letter/invoice/blog/other",
        "summary": "brief summary"
    }}
    
    Text: {text[:2000]}"""  # Only send first 2000 characters to save tokens
    
    # Send request to local LM Studio server
    response = requests.post("http://localhost:1234/v1/chat/completions", 
        json={
            "model": "local-model",  # Your local model name
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1  # Low temperature for consistent results
        })
    
    # STEP 4: RETURN STRUCTURED JSON OUTPUT
    if response.status_code == 200:
        # Get the LLM's response
        llm_result = response.json()['choices'][0]['message']['content']
        
        # Extract JSON from the response (removes markdown formatting)
        json_start = llm_result.find('{')  # Find first {
        json_end = llm_result.rfind('}') + 1  # Find last }
        json_text = llm_result[json_start:json_end]  # Extract JSON part
        
        # Parse and return the JSON
        return json.loads(json_text)
    else:
        return {"error": "LM Studio connection failed"}

# MAIN EXECUTION
if __name__ == "__main__":
    # Specify the document to process
    file_path = "testnow.pdf" 
    
    # Process the document
    result = process_document(file_path)
    
    # Print the final result in pretty JSON format
    print(json.dumps(result, indent=2))