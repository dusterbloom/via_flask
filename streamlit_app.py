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
                if available_documents:
                    st.write("### Available Documents")
                    st.write("Click on the links to open documents in a new tab:")
                    
                    for doc in available_documents:
                        st.markdown(f"""
                        - [Document]({doc['url']})
                          - Project: [{doc['project_url']}]({doc['project_url']})
                          - Procedure: [{doc['procedure_url']}]({doc['procedure_url']})
                        """)
                        
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")