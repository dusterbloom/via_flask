import os
import re
import time
import urllib.parse
import requests
from bs4 import BeautifulSoup
from typing import Tuple, List, Dict, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
BASE_URL = "https://va.mite.gov.it"
SEARCH_ENDPOINT = "/it-IT/Ricerca/ViaLibera"
DOWNLOAD_FOLDER = "downloads"
DELAY_BETWEEN_REQUESTS = 1.0  # Reduced from 2.0 since we're using sessions effectively

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

class ScraperSession:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.session.get(BASE_URL)  # Initialize session with cookies
    
    def get(self, url: str, **kwargs) -> requests.Response:
        return self.session.get(url, **kwargs)

def get_filename_from_response(response: requests.Response) -> str:
    """Extract filename from response headers or URL."""
    content_disposition = response.headers.get("Content-Disposition", "")
    filename = None
    
    if content_disposition:
        match = re.search(r'filename\*?=(["\']?)(.*?)\1(?:;|$)', content_disposition)
        if match:
            filename_candidate = match.group(2).strip()
            filename_candidate = filename_candidate.strip('"').split('/')[-1]
            if filename_candidate:
                filename = filename_candidate
    
    if not filename:
        filename = os.path.basename(urllib.parse.urlsplit(response.url).path)
        if not filename:
            filename = f"doc_{int(time.time())}.pdf"
    
    if not os.path.splitext(filename)[1]:
        filename += ".pdf"
    
    return filename

def get_projects(keyword: str) -> Tuple[List[str], ScraperSession]:
    """Get all project URLs for a given keyword."""
    scraper_session = ScraperSession()
    all_project_links = []
    current_page = 1
    
    while True:
        search_url = f"{BASE_URL}{SEARCH_ENDPOINT}?Testo={urllib.parse.quote(keyword)}&t=o&p={current_page}"
        logger.info(f"Searching page {current_page} with keyword='{keyword}'")

        try:
            resp = scraper_session.get(search_url, timeout=10)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            project_links = [
                urllib.parse.urljoin(BASE_URL, a["href"])
                for a in soup.find_all("a", href=True)
                if "/it-IT/Oggetti/Info/" in a["href"]
            ]

            if not project_links:
                break
                
            all_project_links.extend(project_links)
            logger.info(f"Found {len(project_links)} project links on page {current_page}")
            
            # Check for next page
            if not any(f"p={current_page + 1}" in a["href"] for a in soup.find_all("a", href=True)):
                break
                
            current_page += 1
            time.sleep(DELAY_BETWEEN_REQUESTS)

        except Exception as e:
            logger.error(f"Failed to get projects on page {current_page}: {e}")
            break

    logger.info(f"Total projects found: {len(all_project_links)}")
    return all_project_links, scraper_session

def get_procedura_links(project_url: str, session: ScraperSession) -> List[str]:
    """Get all procedure URLs for a given project."""
    logger.info(f"Parsing project page => {project_url}")
    
    try:
        resp = session.get(project_url, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        procedura_links = [
            urllib.parse.urljoin(project_url, a["href"])
            for a in soup.find_all("a", href=True)
            if "/it-IT/Oggetti/Documentazione/" in a["href"]
        ]

        logger.info(f"Found {len(procedura_links)} procedure links")
        return procedura_links

    except Exception as e:
        logger.error(f"Failed to get procedure links for {project_url}: {e}")
        return []

def get_document_links(procedura_url: str, session: ScraperSession) -> List[str]:
    """Get all document URLs from a procedure page."""
    all_doc_links = []
    current_page = 1
    
    while True:
        page_url = procedura_url if current_page == 1 else f"{procedura_url}?pagina={current_page}"
        logger.info(f"Parsing procedure page {current_page}")
        
        try:
            resp = session.get(page_url, timeout=30)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            doc_links = [
                urllib.parse.urljoin(procedura_url, a["href"])
                for a in soup.find_all("a", href=True)
                if "/File/Documento/" in a["href"]
            ]

            if not doc_links:
                break
                
            all_doc_links.extend(doc_links)
            logger.info(f"Found {len(doc_links)} document links on page {current_page}")
            
            if not any(f"pagina={current_page + 1}" in a["href"] for a in soup.find_all("a", href=True)):
                break
                
            current_page += 1
            time.sleep(DELAY_BETWEEN_REQUESTS)

        except Exception as e:
            logger.error(f"Failed to get documents on page {current_page}: {e}")
            break

    return all_doc_links

def get_document_metadata(doc_url: str, session: ScraperSession) -> Optional[Dict]:
    """Get metadata for a document."""
    try:
        response = session.get(doc_url, stream=True, timeout=10)
        response.raise_for_status()
        
        filename = get_filename_from_response(response)
        
        return {
            'url': doc_url,
            'filename': filename,
            'size': response.headers.get('Content-Length', 'Unknown'),
            'type': response.headers.get('Content-Type', 'Unknown'),
            'last_modified': response.headers.get('Last-Modified', 'Unknown')
        }
        
    except Exception as e:
        logger.error(f"Failed to get document metadata for {doc_url}: {e}")
        return None

def download_document(doc_url: str, session: ScraperSession) -> Optional[bytes]:
    """Download a document and return its content."""
    try:
        response = session.get(doc_url, stream=True, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.error(f"Failed to download document {doc_url}: {e}")
        return None