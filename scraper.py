import os
import re
import time
import urllib.parse
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://va.mite.gov.it"
SEARCH_ENDPOINT = "/it-IT/Ricerca/ViaLibera"
DOWNLOAD_FOLDER = "downloads"
DELAY_BETWEEN_REQUESTS = 2.0


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}



if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)


def build_search_url(keyword: str, search_type="o"):
    params = {
        "Testo": keyword,
        "t": search_type  # 'o' = progetti, 'd' = documenti
    }
    return f"{BASE_URL}{SEARCH_ENDPOINT}?{urllib.parse.urlencode(params)}"


def download_file(doc_url: str, session=None):
    if session is None:
        session = requests.Session()

    try:
        print(f"[INFO] Downloading: {doc_url}")
        with session.get(doc_url, stream=True, timeout=20) as r:
            r.raise_for_status()

            content_disposition = r.headers.get("Content-Disposition", "")
            filename = None

            if content_disposition:
                match = re.search(r'filename\*?=(["\']?)(.*?)\1(?:;|$)', content_disposition)
                if match:
                    filename_candidate = match.group(2).strip()
                    filename_candidate = filename_candidate.strip('"').split('/')[-1]
                    if filename_candidate:
                        filename = filename_candidate

            if not filename:
                filename = os.path.basename(urllib.parse.urlsplit(doc_url).path)
                if not filename:
                    filename = f"doc_{int(time.time())}.pdf"

            if not os.path.splitext(filename)[1]:
                filename += ".pdf"

            local_path = os.path.join(DOWNLOAD_FOLDER, filename)

            if os.path.exists(local_path):
                print(f"[INFO] '{filename}' already exists, skipping.")
                return

            with open(local_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        print(f"[OK] Saved => {local_path}")

    except Exception as e:
        print(f"[ERROR] Download failed for {doc_url}: {e}")

def get_projects(keyword: str, max_results=None):
    """
    Get project URLs from search results with pagination support
    
    Args:
        keyword (str): Search keyword
        max_results (int, optional): Maximum number of results to return. None for all results.
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    
    all_project_links = []
    page = 1
    
    while True:
        # Build URL with pagination
        search_url = build_search_url(keyword, search_type="o", page=page)
        print(f"[INFO] Searching page {page} with keyword='{keyword}' => {search_url}")

        try:
            if page == 1:
                # Get main page for cookies only on first request
                session.get(BASE_URL)
            
            resp = session.get(search_url, timeout=10)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Find project links on current page
            page_links = []
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if "/it-IT/Oggetti/Info/" in href:
                    full_url = urllib.parse.urljoin(BASE_URL, href)
                    page_links.append(full_url)
            
            if not page_links:
                # No more results found
                break
                
            all_project_links.extend(page_links)
            
            # Check if we've reached max_results
            if max_results and len(all_project_links) >= max_results:
                all_project_links = all_project_links[:max_results]
                break
            
            # Check for next page
            next_page = soup.find("a", class_="next") or soup.find("a", text="»")
            if not next_page:
                break
                
            page += 1
            
        except Exception as e:
            print(f"[ERROR] Failed to get projects on page {page}: {e}")
            break

    print(f"[INFO] Found total of {len(all_project_links)} project detail links")
    return all_project_links, session

def build_search_url(keyword: str, search_type="o", page=1):
    """Build search URL with pagination support"""
    params = {
        "Testo": keyword,
        "t": search_type,  # 'o' = progetti, 'd' = documenti
        "p": page  # Add page parameter
    }
    return f"{BASE_URL}{SEARCH_ENDPOINT}?{urllib.parse.urlencode(params)}"

def get_procedura_links(project_url: str, session=None):
    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)
    
    print(f"[INFO] Parsing project page => {project_url}")
    resp = session.get(project_url, timeout=10)
    if resp.status_code != 200:
        print(f"[WARN] Could not retrieve {project_url} (status={resp.status_code}).")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    procedura_links = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/it-IT/Oggetti/Documentazione/" in href:
            full_url = urllib.parse.urljoin(project_url, href)
            procedura_links.append(full_url)

    print(f"[INFO] Found {len(procedura_links)} procedure links on this project.")
    return procedura_links


def get_document_links(procedura_url: str, session=None):
    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)
    
    print(f"[INFO] Parsing procedure page => {procedura_url}")
    resp = session.get(procedura_url, timeout=10)
    if resp.status_code != 200:
        print(f"[WARN] Could not retrieve {procedura_url} (status={resp.status_code}).")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    documents = []

    # Find all document links
    for link in soup.find_all("a", href=True):
        href = link["href"]
        # Expand document types to include common formats
        if any(ext in href.lower() for ext in [
            '/file/documento/',  # Generic document path
            '.pdf', 
            '.doc', 
            '.docx', 
            '.xls', 
            '.xlsx',
            '.zip',
            '.rar',
            '.7z',
            '.txt',
            '.rtf'
        ]):
            doc_data = {
                "url": urllib.parse.urljoin(BASE_URL, href),
                "title": link.get_text(strip=True) or "Untitled Document",
                "date": "N/A",
                "type": "Document",
                "size": "N/A",
                "extension": href.split('.')[-1].lower() if '.' in href else 'unknown'
            }
            
            # Try to find metadata in parent elements
            parent_div = link.find_parent("div", class_="documento")
            if parent_div:
                metadata_div = parent_div.find("div", class_="metadata")
                if metadata_div:
                    date_span = metadata_div.find("span", class_="data")
                    type_span = metadata_div.find("span", class_="tipo")
                    size_span = metadata_div.find("span", class_="dimensione")
                    
                    doc_data["date"] = date_span.get_text(strip=True) if date_span else "N/A"
                    doc_data["type"] = type_span.get_text(strip=True) if type_span else "Document"
                    doc_data["size"] = size_span.get_text(strip=True) if size_span else "N/A"
            
            documents.append(doc_data)

    print(f"[INFO] Found {len(documents)} documents with metadata")
    return documents

def run_scraper(keyword: str):
    # 1) Gather project detail URLs with session
    project_urls, session = get_projects(keyword)

    for project_url in project_urls:
        try:
            # 2) For each project, gather procedure pages
            procedure_urls = get_procedura_links(project_url, session)

            for proc_url in procedure_urls:
                # 3) Gather the final doc links
                doc_urls = get_document_links(proc_url, session)

                # 4) Download them
                for durl in doc_urls:
                    download_file(durl, session)
                    time.sleep(DELAY_BETWEEN_REQUESTS)

            # Wait a bit between projects
            time.sleep(DELAY_BETWEEN_REQUESTS)
            
        except Exception as e:
            print(f"[ERROR] Failed processing project {project_url}: {e}")
            continue