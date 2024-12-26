import streamlit as st
import os
from scraper import get_projects, get_procedura_links, get_document_links, download_file
import time
import base64
import tempfile
import zipfile

# Function to create a download link for a file
def get_binary_file_downloader_html(file_path, file_label):
    with open(file_path, 'rb') as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{os.path.basename(file_path)}">{file_label}</a>'

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
            filename = f"{doc['title']}.pdf" if doc['title'] else doc['url'].split('/')[-1]
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

# Create downloads directory if it doesn't exist
if not os.path.exists("downloads"):
    os.makedirs("downloads")

# Title and description
st.title("🔍 VIA Database Search")
st.markdown("""
This tool allows you to search and preview documents from the VIA Database.
Enter a keyword below to start searching.
""")

# Show download folder path
st.info(f"Downloads folder: {os.path.abspath('downloads')}")

# Search input
keyword = st.text_input("Enter a keyword:", key="search_keyword")
search_button = st.button("Search")

if search_button and keyword:
    keyword = keyword.strip()
    if not keyword:
        st.error("Please enter a valid keyword.")
    else:
        try:
            with st.spinner("Searching for projects..."):
                # Get project URLs and session
                project_urls, session = get_projects(keyword)
                st.info(f"Found {len(project_urls)} projects")

                results = []

                for i, project_url in enumerate(project_urls):
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
                                selected_docs = project_docs
                            
                            # Display documents
                            for doc in project_docs:
                                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                                with col1:
                                    st.markdown(f"**{doc['title']}**")
                                with col2:
                                    st.markdown(f"""
                                    📅 {doc['date']}  
                                    📁 {doc['type']}  
                                    💾 {doc['size']}
                                    """)
                                with col3:
                                    # Individual selection checkbox
                                    if st.checkbox("Select", key=f"select_{doc['url']}", 
                                                 value=doc in selected_docs):
                                        if doc not in selected_docs:
                                            selected_docs.append(doc)
                                with col4:
                                    # Individual download button
                                    if st.button(f"Download", key=f"download_{doc['url']}"):
                                        try:
                                            download_file(doc['url'], session)
                                            st.success("File downloaded!")
                                        except Exception as e:
                                            st.error(f"Download failed: {str(e)}")
                                st.markdown("---")

                # Download selected documents
                if selected_docs:
                    st.markdown("### Download Selected Documents")
                    if st.button("Download Selected"):
                        try:
                            # Create a temporary directory for the zip file
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_zip:
                                # Download all selected files
                                files_dict = download_multiple_files(selected_docs, session)
                                # Create zip file
                                create_zip_of_files(files_dict, tmp_zip.name)
                                # Offer zip file for download
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

# Show downloaded files with download buttons
if os.path.exists("downloads"):
    with st.expander("View and Download Files"):
        files = os.listdir("downloads")
        if files:
            st.write("Downloaded files:")
            for file in files:
                file_path = os.path.join("downloads", file)
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"📄 {file}")
                with col2:
                    st.markdown(
                        get_binary_file_downloader_html(
                            file_path, 
                            "Download"
                        ),
                        unsafe_allow_html=True
                    )
                st.markdown("---")
        else:
            st.write("No files downloaded yet.")

# Add a clear downloads button
if st.button("Clear Downloads Folder"):
    try:
        for file in os.listdir("downloads"):
            os.remove(os.path.join("downloads", file))
        st.success("Downloads folder cleared!")
    except Exception as e:
        st.error(f"Error clearing downloads: {str(e)}")