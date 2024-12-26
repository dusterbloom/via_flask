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

def build_search_url(keyword: str, search_type="o", page=1):
    params = {
        "Testo": keyword,
        "t": search_type,  # 'o' = progetti, 'd' = documenti
        "p": page  # Add page parameter
    }
    return f"{BASE_URL}{SEARCH_ENDPOINT}?{urllib.parse.urlencode(params)}"

def get_projects(keyword: str):
    session = requests.Session()
    session.headers.update(HEADERS)
    
    all_project_links = []
    current_page = 1
    
    while True:
        search_url = build_search_url(keyword, search_type="o", page=current_page)
        print(f"[INFO] Searching page {current_page} with keyword='{keyword}' => {search_url}")

        try:
            # First page only: get the main page to obtain any necessary cookies
            if current_page == 1:
                session.get(BASE_URL)
            
            # Get the search results page
            resp = session.get(search_url, timeout=10)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Find project links on current page
            project_links = []
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if "/it-IT/Oggetti/Info/" in href:
                    full_url = urllib.parse.urljoin(BASE_URL, href)
                    project_links.append(full_url)

            if not project_links:  # No more results found
                break
                
            all_project_links.extend(project_links)
            print(f"[INFO] Found {len(project_links)} project links on page {current_page}")
            
            # Check if there's a next page by looking for pagination links
            next_page_exists = False
            for a_tag in soup.find_all("a", href=True):
                if f"p={current_page + 1}" in a_tag["href"]:
                    next_page_exists = True
                    break
            
            if not next_page_exists:
                break
                
            current_page += 1
            time.sleep(DELAY_BETWEEN_REQUESTS)  # Be nice to the server between page requests

        except Exception as e:
            print(f"[ERROR] Failed to get projects on page {current_page}: {e}")
            break

    print(f"[INFO] Total projects found across {current_page} pages: {len(all_project_links)}")
    return all_project_links, session

def get_document_info(doc_url: str, session=None):
    if session is None:
        session = requests.Session()
    
    try:
        # Just get the headers to check file info
        r = session.head(doc_url, timeout=10)
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
            
        return {
            'url': doc_url,
            'filename': filename,
            'size': r.headers.get('Content-Length', 'Unknown'),
            'type': r.headers.get('Content-Type', 'Unknown')
        }
        
    except Exception as e:
        print(f"[ERROR] Failed to get document info for {doc_url}: {e}")
        return None
    

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
    
    all_doc_links = []
    current_page = 1
    
    while True:
        # Construct URL with pagination
        page_url = procedura_url
        if current_page > 1:
            page_url = f"{procedura_url}?pagina={current_page}"
            
        print(f"[INFO] Parsing procedure page {current_page} => {page_url}")
        
        try:
            resp = session.get(page_url, timeout=1000)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            doc_links = []

            # Find document links on current page
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if "/File/Documento/" in href:
                    doc_url = urllib.parse.urljoin(procedura_url, href)
                    doc_links.append(doc_url)

            if not doc_links:  # No documents found on this page
                break
                
            all_doc_links.extend(doc_links)
            print(f"[INFO] Found {len(doc_links)} doc links on page {current_page}")
            
            # Check if there's a next page by looking for pagination links
            next_page_exists = False
            pagination_links = soup.find_all("a", href=True)
            for link in pagination_links:
                if f"pagina={current_page + 1}" in link["href"]:
                    next_page_exists = True
                    break
            
            if not next_page_exists:
                break
                
            current_page += 1
            time.sleep(DELAY_BETWEEN_REQUESTS)  # Be nice to the server

        except Exception as e:
            print(f"[ERROR] Failed to get documents on page {current_page}: {e}")
            break

    print(f"[INFO] Total documents found across {current_page} pages: {len(all_doc_links)}")
    return all_doc_links

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