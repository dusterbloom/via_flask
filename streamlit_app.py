import streamlit as st
import os
from scraper import get_projects, get_procedura_links, get_document_links
import time
import tempfile
import zipfile

def get_file_extension(doc):
    """Get appropriate file extension based on document type or URL"""
    # Try to get extension from URL first
    url = doc['url'].lower()
    for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.rar', '.7z', '.txt', '.rtf']:
        if ext in url:
            return ext
    
    # Fallback to type-based extension
    type_mapping = {
        'PDF': '.pdf',
        'WORD': '.doc',
        'EXCEL': '.xls',
        'DOCUMENTO': '.pdf',
        'ARCHIVIO': '.zip',
        'TESTO': '.txt'
    }
    
    doc_type = doc.get('type', '').upper()
    for key, ext in type_mapping.items():
        if key in doc_type:
            return ext
    
    return '.pdf'  # Default fallback

def create_zip_of_files(files_dict, zip_path):
    """Create a zip file containing multiple documents"""
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for filename, file_data in files_dict.items():
            zipf.writestr(filename, file_data)

def download_multiple_files(urls, session):
    """Download multiple files and return them as a dictionary"""
    files_dict = {}
    for doc in urls:
        try:
            response = session.get(doc['url'], stream=True)
            response.raise_for_status()
            
            # Get appropriate extension
            extension = get_file_extension(doc)
            
            # Create filename with proper extension
            filename = f"{doc['title']}{extension}"
            # Clean filename of invalid characters
            filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.'))
            
            files_dict[filename] = response.content
        except Exception as e:
            st.warning(f"Failed to download {doc['title']}: {str(e)}")
    return files_dict

# Page config
st.set_page_config(
    page_title="VIA Database Search",
    page_icon="🔍",
    layout="wide"
)

# Title and description
st.title("🔍 VIA Database Search")
st.markdown("""
This tool allows you to search and preview documents from the VIA Database.
Enter a keyword below to start searching.
""")

# Search controls
col1, col2 = st.columns([3, 1])
with col1:
    keyword = st.text_input("Enter a keyword:", key="search_keyword")
with col2:
    max_results = st.number_input("Max projects (0 = all):", 
                                min_value=0, 
                                value=10)

search_button = st.button("Search")

if search_button and keyword:
    keyword = keyword.strip()
    if not keyword:
        st.error("Please enter a valid keyword.")
    else:
        try:
            with st.spinner("Searching for projects..."):
                # Get project URLs and session
                project_urls, session = get_projects(keyword, 
                                                  max_results=max_results if max_results > 0 else None)
                st.info(f"Found {len(project_urls)} projects")

                results = []
                progress = st.progress(0)

                for i, project_url in enumerate(project_urls):
                    progress.progress((i + 1) / len(project_urls))
                    st.text(f"Scanning project {i+1}/{len(project_urls)}...")
                    
                    # Get procedure pages
                    procedure_urls = get_procedura_links(project_url, session)

                    for proc_url in procedure_urls:
                        # Get documents with metadata
                        documents = get_document_links(proc_url, session)
                        
                        # Add project and procedure info to each document
                        for doc in documents:
                            doc.update({
                                'project_url': project_url,
                                'procedure_url': proc_url,
                                'project_number': i+1
                            })
                            results.append(doc)

                # Display results
                st.success(f"Found {len(results)} documents across {len(project_urls)} projects")
                
                # Initialize selected docs list
                selected_docs = []
                
                # Group documents by project
                for i in range(len(project_urls)):
                    project_docs = [r for r in results if r['project_number'] == i+1]
                    if project_docs:
                        with st.expander(f"Project #{i+1} - {len(project_docs)} documents"):
                            # Add project link
                            st.markdown(f"🔗 [View Project Details]({project_docs[0]['project_url']})")
                            st.markdown("---")
                            
                            # Add "Select All" for this project
                            if st.checkbox(f"Select all documents from Project #{i+1}", key=f"select_all_{i}"):
                                selected_docs.extend(project_docs)
                            
                            # Display documents
                            # Display documents
                            for doc in project_docs:
                                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                                with col1:
                                    # Display document name
                                    st.markdown(f"📄 {doc['title']}")
                                
                                with col2:
                                    # Display status indicators
                                    st.markdown("""
                                    📊 N/A  
                                    📁 Document  
                                    📏 N/A
                                    """)
                                
                                with col3:
                                    # Single checkbox for selection
                                    if st.checkbox("Select", key=f"select_{doc['url']}", 
                                                value=doc in selected_docs):
                                        if doc not in selected_docs:
                                            selected_docs.append(doc)
                                
                                with col4:
                                    # Single download button
                                    st.download_button(
                                        label="Download",
                                        data=session.get(doc['url']).content if doc['url'] else None,
                                        file_name=doc['title'],
                                        mime="application/octet-stream",
                                        key=f"download_{doc['url']}"
                                    )
                                
                                st.markdown("---")

                            # For batch downloads
                            if selected_docs:
                                st.markdown("### Download Selected Documents")
                                col1, col2 = st.columns([1, 3])
                                with col1:
                                    st.write(f"Selected: {len(selected_docs)} documents")
                                with col2:
                                    # Create ZIP file only when user clicks download
                                    if st.button("Download Selected"):
                                        try:
                                            with st.spinner("Preparing ZIP file..."):
                                                with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_zip:
                                                    files_dict = {}
                                                    for doc in selected_docs:
                                                        response = session.get(doc['url'])
                                                        files_dict[doc['title']] = response.content
                                                    
                                                    create_zip_of_files(files_dict, tmp_zip.name)
                                                    
                                                    with open(tmp_zip.name, 'rb') as f:
                                                        st.download_button(
                                                            label="Save ZIP File",
                                                            data=f,
                                                            file_name=f"VIA_documents_{keyword}.zip",
                                                            mime="application/zip"
                                                        )
                                        except Exception as e:
                                            st.error(f"Failed to create zip file: {str(e)}")


        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.error("Debug info:")
            import traceback
            st.code(traceback.format_exc())