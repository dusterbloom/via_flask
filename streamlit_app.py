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

# Show download folder path
st.info(f"Downloads folder: {os.path.abspath('downloads')}")



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
                project_urls, session = get_projects(keyword)  # Make sure to unpack both values
                  # Apply the project limit if specified
                if max_projects > 0:
                    project_urls = project_urls[:max_projects]
                st.info(f"Found {len(project_urls)} projects to process")
                
                # Create a progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()

                # Initialize counters
                total_procedures = 0
                total_documents = 0
                
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

                        # 4) Download documents - pass the session
                        for doc_url in doc_urls:
                            download_file(doc_url, session)
                            time.sleep(2.0)  # Respect rate limiting

                    # Update progress
                    progress = (i + 1) / len(project_urls)
                    progress_bar.progress(progress)

                # Show final results
                st.success(f"""
                Scraping completed successfully!
                - Projects processed: {len(project_urls)}
                - Total procedures found: {total_procedures}
                - Total documents downloaded: {total_documents}
                
                Check the 'downloads' folder for the downloaded files.
                """)

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            # Add debug information
            st.error("Debug info:")
            st.code(str(e.__class__.__name__))
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