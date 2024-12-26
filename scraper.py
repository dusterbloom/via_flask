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


def get_projects(keyword: str):
    search_url = build_search_url(keyword, search_type="o")
    print(f"[INFO] Searching for projects with keyword='{keyword}' => {search_url}")

    resp = requests.get(search_url, timeout=10)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    project_links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/it-IT/Oggetti/Info/" in href:
            full_url = urllib.parse.urljoin(BASE_URL, href)
            project_links.append(full_url)

    print(f"[INFO] Found {len(project_links)} project detail links.")
    return project_links


def get_procedura_links(project_url: str):
    print(f"[INFO] Parsing project page => {project_url}")
    resp = requests.get(project_url, timeout=10)
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


def get_document_links(procedura_url: str):
    print(f"[INFO] Parsing procedure page => {procedura_url}")
    resp = requests.get(procedura_url, timeout=10)
    if resp.status_code != 200:
        print(f"[WARN] Could not retrieve {procedura_url} (status={resp.status_code}).")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    doc_links = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/File/Documento/" in href:
            doc_url = urllib.parse.urljoin(procedura_url, href)
            doc_links.append(doc_url)

    print(f"[INFO] Found {len(doc_links)} doc links on this procedure.")
    return doc_links


def run_scraper(keyword: str):
    # 1) Gather project detail URLs
    project_urls = get_projects(keyword)

    for project_url in project_urls:
        # 2) For each project, gather procedure pages
        procedure_urls = get_procedura_links(project_url)

        for proc_url in procedure_urls:
            # 3) Gather the final doc links
            doc_urls = get_document_links(proc_url)

            # 4) Download them
            for durl in doc_urls:
                download_file(durl)
                time.sleep(DELAY_BETWEEN_REQUESTS)

        # Wait a bit between projects
        time.sleep(DELAY_BETWEEN_REQUESTS)
