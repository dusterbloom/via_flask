import streamlit as st
import os
from scraper import run_scraper, get_projects, get_procedura_links, get_document_links, download_file
import time
import base64



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
                project_urls, session = get_projects(keyword)
                if max_projects > 0:
                    project_urls = project_urls[:max_projects]
                st.info(f"Found {len(project_urls)} projects to process")
                
                # Create a progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()

                # Initialize counters and document storage
                total_procedures = 0
                total_documents = 0
                available_documents = []  # New list to store document info
                
                # Process each project
                for i, project_url in enumerate(project_urls):
                    status_text.text(f"Processing project {i+1}/{len(project_urls)}")
                    
                    # 2) Get procedure pages - pass the session
                    procedure_urls = get_procedura_links(project_url, session)
                    total_procedures += len(procedure_urls)

                    for proc_url in procedure_urls:
                        # 3) Get document links - pass the session
                        doc_urls = get_document_links(proc_url, session)
                        total_documents += len(doc_urls)
                        
                        # Store document URLs instead of downloading
                        for doc_url in doc_urls:
                            available_documents.append({
                                'url': doc_url,
                                'project_url': project_url,
                                'procedure_url': proc_url
                            })

                # Show final results
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
                            # Fetch metadata using the same session
                            metadata_response = session.get(metadata_url)
                            metadata_response.raise_for_status()
                            
                            soup = BeautifulSoup(metadata_response.text, 'html.parser')
                            doc_title = soup.find('td', text='Documento').find_next('td').text.strip()
                            
                            st.markdown(f"""
                            - [{doc_title}]({doc['url']})
                            - Project: [{doc['project_url']}]({doc['project_url']})
                            - Procedure: [{doc['procedure_url']}]({doc['procedure_url']})
                            """)
                        except Exception as e:
                            # Fallback to the URL filename if metadata fetch fails
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