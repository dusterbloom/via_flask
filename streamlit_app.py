import streamlit as st
import os
from scraper import run_scraper, get_projects, get_procedura_links, get_document_links, download_file
import time
import base64

from bs4 import BeautifulSoup  # Add this if not already imported


# Function to create a download link for a file
def get_binary_file_downloader_html(file_path, file_label):
    with open(file_path, 'rb') as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{os.path.basename(file_path)}">{file_label}</a>'


# Page config
st.set_page_config(
    page_title="VIA Database Scraper",
    page_icon="🔍",
    layout="wide"
)

# Create downloads directory if it doesn't exist
if not os.path.exists("downloads"):
    os.makedirs("downloads")


# Title and description
st.title("🔍 VIA Database Search")
st.markdown("""
This tool allows you to search and download documents from the VIA Database.
Enter a keyword below to start searching.
""")

# Search input
keyword = st.text_input("Enter a keyword:", key="search_keyword")
max_projects = st.number_input("Maximum number of projects to process (0 for all):", 
                             min_value=0, 
                             value=0, 
                             help="Set to 0 to process all found projects")
search_button = st.button("Run Scraper")

if search_button and keyword:
    keyword = keyword.strip()
    if not keyword:
        st.error("Please enter a valid keyword.")
    else:
        try:
            with st.spinner("Searching for projects..."):
                # 1) Get project URLs and session
                project_urls, session = get_projects(keyword)  # This now handles pagination internally
                
                if project_urls:
                    st.success(f"Found {len(project_urls)} projects across multiple pages")
                else:
                    st.warning("No projects found for this keyword.")
                    st.stop()
                
                if max_projects > 0:
                    project_urls = project_urls[:max_projects]
                    st.info(f"Processing first {max_projects} projects as requested")
                
                # Create a progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()

                # Initialize counters and document storage
                total_procedures = 0
                total_documents = 0
                available_documents = []
                
                # Process each project
                for i, project_url in enumerate(project_urls):
                    # Update progress
                    progress = (i + 1) / len(project_urls)
                    progress_bar.progress(progress)
                    status_text.text(f"Processing project {i+1}/{len(project_urls)}")
                    
                    try:
                        procedure_urls = get_procedura_links(project_url, session)
                        total_procedures += len(procedure_urls)

                        # Inside the main search loop, update the status messages:
                        for proc_url in procedure_urls:
                            status_text.text(f"Processing project {i+1}/{len(project_urls)} - Fetching documents from procedure...")
                            doc_urls = get_document_links(proc_url, session)
                            total_documents += len(doc_urls)
                            
                            for doc_url in doc_urls:
                                available_documents.append({
                                    'url': doc_url,
                                    'project_url': project_url,
                                    'procedure_url': proc_url,
                                    'date_found': time.strftime('%Y-%m-%d %H:%M:%S')  # Optional: add timestamp
                                })
                            
                            # Add a small delay between requests
                            time.sleep(2)
                            
                    except Exception as e:
                        st.warning(f"Error processing project {project_url}: {str(e)}")
                        continue

                # Show final results
                progress_bar.empty()
                status_text.empty()
                st.success(f"""
                Search completed successfully!
                - Projects processed: {len(project_urls)}
                - Total procedures found: {total_procedures}
                - Total documents available: {total_documents}
                """)

                                # Display available documents in a table
                # Add this after the document processing loop (around line 95)
                if available_documents:
                    # Pagination controls
                    docs_per_page = 10
                    total_pages = len(available_documents) // docs_per_page + (1 if len(available_documents) % docs_per_page > 0 else 0)
                    
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col2:
                        current_page = st.selectbox("Page", options=range(1, total_pages + 1), format_func=lambda x: f"Page {x} of {total_pages}")
                    
                    start_idx = (current_page - 1) * docs_per_page
                    end_idx = min(start_idx + docs_per_page, len(available_documents))
                    
                    st.write("Click on the links to open documents in a new tab:")
                    
                    # Display only the documents for the current page
                    for doc in available_documents[start_idx:end_idx]:
                        # Extract document ID from URL
                        doc_id = doc['url'].split('/')[-1]
                        # Construct metadata URL
                        metadata_url = f"https://va.mite.gov.it/it-IT/Oggetti/MetadatoDocumento/{doc_id}"
                        
                        try:
                            metadata_response = session.get(metadata_url)
                            metadata_response.raise_for_status()
                            
                            soup = BeautifulSoup(metadata_response.text, 'html.parser')
                            doc_title_element = soup.find('td', text='Documento')
                            
                            if doc_title_element and doc_title_element.find_next('td'):
                                doc_title = doc_title_element.find_next('td').text.strip()
                            else:
                                raise ValueError("Document title not found in metadata")
                                
                            st.markdown(f"""
                            - [{doc_title}]({doc['url']})
                            - Project: [{doc['project_url']}]({doc['project_url']})
                            - Procedure: [{doc['procedure_url']}]({doc['procedure_url']})
                            """)
                        except Exception as e:
                            # More detailed error logging
                            print(f"Error fetching metadata for {doc['url']}: {str(e)}")
                            # Fallback to the URL filename
                            from urllib.parse import unquote
                            filename = unquote(doc['url'].split('fileName=')[-1]) if 'fileName=' in doc['url'] else doc['url'].split('/')[-1]
                            st.markdown(f"""
                            - [{filename}]({doc['url']})
                            - Project: [{doc['project_url']}]({doc['project_url']})
                            - Procedure: [{doc['procedure_url']}]({doc['procedure_url']})
                            """)
                    # Add page navigation buttons
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col1:
                        if current_page > 1:
                            if st.button("← Previous"):
                                st.session_state['current_page'] = current_page - 1
                                st.rerun()
                    with col3:
                        if current_page < total_pages:
                            if st.button("Next →"):
                                st.session_state['current_page'] = current_page + 1
                                st.rerun()
                        
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")