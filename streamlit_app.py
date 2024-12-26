import streamlit as st
import os
import re
import requests
from scraper import (
    get_project_info,
    get_projects, 
    get_procedura_links, 
    get_document_links,
    HEADERS,  # Import constants from scraper
    BASE_URL,
    ScraperSession
)
import time
import base64
import zipfile
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import unquote

# Initialize session state
if 'search_results' not in st.session_state:
    st.session_state['search_results'] = None
if 'current_page' not in st.session_state:
    st.session_state['current_page'] = 1
if 'available_documents' not in st.session_state:
    st.session_state['available_documents'] = []
if 'scraper_session' not in st.session_state:
    st.session_state['scraper_session'] = ScraperSession()

# Cached functions for expensive operations
@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_projects(keyword, max_projects):
    project_urls, _ = get_projects(keyword)
    if max_projects > 0:
        project_urls = project_urls[:max_projects]
    return project_urls

@st.cache_data(ttl=3600)
def fetch_documents(project_url, _session):
    procedure_urls = get_procedura_links(project_url, _session)
    documents = []
    for proc_url in procedure_urls:
        doc_urls = get_document_links(proc_url, _session)
        for doc_url in doc_urls:
            documents.append({
                'url': doc_url,
                'project_url': project_url,
                'procedure_url': proc_url,
                'date_found': time.strftime('%Y-%m-%d %H:%M:%S')
            })
    return documents, len(procedure_urls)

@st.cache_data(ttl=600)  # Cache for 10 minutes
def create_zip_of_documents(documents, _session):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = f"downloads/documents_{timestamp}.zip"
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for idx, doc in enumerate(documents):
            try:
                response = _session.get(doc['url'], stream=True)
                response.raise_for_status()
                
                filename = None
                content_disposition = response.headers.get('Content-Disposition')
                if content_disposition:
                    import re
                    matches = re.findall('filename=(.+)', content_disposition)
                    if matches:
                        filename = matches[0].strip('"')
                
                if not filename:
                    filename = unquote(doc['url'].split('fileName=')[-1]) if 'fileName=' in doc['url'] else doc['url'].split('/')[-1]
                
                zipf.writestr(filename, response.content)
                time.sleep(0.5)  # Be nice to the server
                
            except Exception as e:
                st.warning(f"Failed to download {doc['url']}: {str(e)}")
                continue
    
    return zip_path



# Page config
st.set_page_config(
    page_title="VIA Database Scraper",
    page_icon="🔍",
    layout="wide"
)

# Create downloads directory
if not os.path.exists("downloads"):
    os.makedirs("downloads")

# UI Elements
st.title("🔍 VIA Database Search")
st.markdown("""
This tool allows you to search and download documents from the VIA Database.
Enter a keyword below to start searching.
""")

# Search inputs
# Search inputs
with st.form("search_form"):
    col1, col2 = st.columns([2, 1])
    
    with col1:
        keyword = st.text_input("Enter a keyword:", key="search_keyword")
    
    with col2:
        id_type = st.selectbox(
            "ID Type:",
            ["Project ID", "Procedure Code"],
            help="Select whether to search by Project ID or Procedure Code"
        )
        project_id = st.text_input(
            f"Enter {id_type}:",
            help="Enter the ID to search for specific project"
        )
    
    col3, col4 = st.columns([2, 1])
    with col3:
        max_projects = st.number_input(
            "Maximum number of projects to process (0 for all):", 
            min_value=0, 
            value=0, 
            help="Set to 0 to process all found projects"
        )
    
    submit_button = st.form_submit_button("Run Scraper")

if submit_button:
    if not keyword.strip() and not project_id.strip():
        st.error("Please enter either a keyword or an ID.")
    else:
        try:
            with st.spinner("Searching for projects..."):
                if project_id:
                    if id_type == "Project ID":
                        # If project ID is provided, create direct URL
                        project_urls = [f"{BASE_URL}/it-IT/Oggetti/Info/{project_id.strip()}"]
                    else:
                        # If procedure code is provided, search for it
                        st.info(f"Searching for procedure code: {project_id}")
                        all_projects = fetch_projects(keyword if keyword else "", 0)
                        project_urls = []
                        
                        # Check each project for matching procedure code
                        for proj_url in all_projects:
                            info = get_project_info(proj_url, st.session_state.scraper_session)
                            if info and info['procedure_code'] == project_id.strip():
                                project_urls.append(proj_url)
                                break
                else:
                    # Get projects using cached function
                    st.info("Fetching projects... This might take a while for large searches.")
                    project_urls = fetch_projects(keyword, max_projects)
                
                if not project_urls:
                    st.warning("No projects found.")
                    st.stop()
                
                if max_projects > 0:
                    project_urls = project_urls[:max_projects]
                    st.info(f"Processing first {max_projects} projects as requested")
                
                # Use the session from session state
                scraper_session = st.session_state.scraper_session
                
                st.success(f"Found {len(project_urls)} projects")
                
                # Process projects
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                total_procedures = 0
                available_documents = []
                
                for i, project_url in enumerate(project_urls):
                    progress = (i + 1) / len(project_urls)
                    progress_bar.progress(progress)
                    status_text.text(f"Processing project {i+1}/{len(project_urls)}")
                    
                    try:
                        docs, proc_count = fetch_documents(project_url, scraper_session)
                        available_documents.extend(docs)
                        total_procedures += proc_count
                    except Exception as e:
                        st.warning(f"Error processing project {project_url}: {str(e)}")
                        continue

                # Show results
                progress_bar.empty()
                status_text.empty()
                st.success(f"""
                Search completed successfully!
                - Projects processed: {len(project_urls)}
                - Total procedures found: {total_procedures}
                - Total documents available: {len(available_documents)}
                """)

                # Display documents with pagination
                if available_documents:
                    st.write("Click on the links to open documents in a new tab:")
                    
                    # Create a container for all documents
                    doc_container = st.container()
                    
                    with doc_container:
                        # Group documents by project
                        project_documents = {}
                        for doc in available_documents:
                            project_id = doc['project_url'].split('/')[-1]
                            if project_id not in project_documents:
                                project_documents[project_id] = []
                            project_documents[project_id].append(doc)
                        
                        # Display documents grouped by project
                        for project_id, docs in project_documents.items():
                            project_info = get_project_info(docs[0]['project_url'], st.session_state.scraper_session)

                            with st.expander(f"Project {project_id} ({len(docs)} documents)", expanded=True):
                                for doc in docs:
                                    doc_id = doc['url'].split('/')[-1]
                                    metadata_url = f"https://va.mite.gov.it/it-IT/Oggetti/MetadatoDocumento/{doc_id}"
                                    
                                    try:
                                        metadata_response = st.session_state.scraper_session.get(metadata_url)
                                        metadata_response.raise_for_status()
                                        
                                        soup = BeautifulSoup(metadata_response.text, 'html.parser')
                                        doc_title_element = soup.find('td', text='Documento')
                                        
                                        if doc_title_element and doc_title_element.find_next('td'):
                                            doc_title = doc_title_element.find_next('td').text.strip()
                                        else:
                                            raise ValueError("Document title not found in metadata")
                                            
                                        st.markdown(f"""
                                        ### Project Information
                                        - **Project ID:** {project_id}
                                        - **Procedure Code:** {project_info['procedure_code'] if project_info else 'Unknown'}
                                        - **Number of Documents:** {len(docs)}
                                        - **Project URL:** [{project_id}]({docs[0]['project_url']})
                                        ---
                                        """)
                                    except Exception as e:
                                        filename = unquote(doc['url'].split('fileName=')[-1]) if 'fileName=' in doc['url'] else doc['url'].split('/')[-1]
                                        st.markdown(f"""
                                        - [{filename}]({doc['url']})
                                        - Project: [{doc['project_url']}]({doc['project_url']})
                                        - Procedure: [{doc['procedure_url']}]({doc['procedure_url']})
                                        ---
                                        """)
                    
                    # Download section
                    st.markdown("---")
                    if available_documents:
                        st.write("Click on the links to open documents in a new tab:")
                        
                        # Add download all button at the top
                        if st.button("Download All Documents"):
                            try:
                                with st.spinner("Creating zip file of all documents..."):
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    zip_path = f"downloads/all_documents_{timestamp}.zip"
                                    
                                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                                        progress_bar = st.progress(0)
                                        for idx, doc in enumerate(available_documents):
                                            try:
                                                response = st.session_state.scraper_session.get(doc['url'], stream=True)
                                                response.raise_for_status()
                                                
                                                # Get filename from URL or content disposition
                                                filename = None
                                                content_disposition = response.headers.get('Content-Disposition')
                                                if content_disposition:
                                                    matches = re.findall('filename=(.+)', content_disposition)
                                                    if matches:
                                                        filename = matches[0].strip('"')
                                                
                                                if not filename:
                                                    filename = unquote(doc['url'].split('fileName=')[-1]) if 'fileName=' in doc['url'] else doc['url'].split('/')[-1]
                                                
                                                # Add project ID prefix to filename to organize files
                                                project_id = doc['project_url'].split('/')[-1]
                                                filename = f"{project_id}_{filename}"
                                                
                                                zipf.writestr(filename, response.content)
                                                
                                                # Update progress
                                                progress = (idx + 1) / len(available_documents)
                                                progress_bar.progress(progress)
                                                time.sleep(0.5)  # Be nice to the server
                                                
                                            except Exception as e:
                                                st.warning(f"Failed to download {doc['url']}: {str(e)}")
                                                continue
                                    
                                    # Offer download of zip file
                                    with open(zip_path, "rb") as fp:
                                        btn = st.download_button(
                                            label="Download ZIP File",
                                            data=fp,
                                            file_name=os.path.basename(zip_path),
                                            mime="application/zip"
                                        )
                                    
                                    st.success("All documents have been zipped successfully! Click the button above to download.")
                                    
                            except Exception as e:
                                st.error(f"Failed to create zip file: {str(e)}")
                    
                    # Navigation buttons
                    col1, col2, col3 = st.columns([1, 2, 1])
       
                    
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")