import streamlit as st
import os
from scraper import run_scraper, get_projects, get_procedura_links, get_document_links, download_file
import time

# Page config
st.set_page_config(
    page_title="VIA Database Scraper",
    page_icon="🔍",
    layout="wide"
)

# Title and description
st.title("🔍 VIA Database Search")
st.markdown("""
This tool allows you to search and download documents from the VIA Database.
Enter a keyword below to start searching.
""")

# Search input
keyword = st.text_input("Enter a keyword:", key="search_keyword")
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
                st.info(f"Found {len(project_urls)} projects")

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

# Show download folder contents
if os.path.exists("downloads"):
    with st.expander("View Downloaded Files"):
        files = os.listdir("downloads")
        if files:
            st.write("Downloaded files:")
            for file in files:
                st.text(f"📄 {file}")
        else:
            st.write("No files downloaded yet.")