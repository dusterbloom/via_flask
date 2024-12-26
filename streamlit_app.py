import streamlit as st
from scraper import get_projects, get_procedura_links, get_document_links
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
This tool allows you to search and preview documents from the VIA Database.
Enter a keyword below to start searching.
""")

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

                # Create containers for results
                results = []

                # Process each project
                for i, project_url in enumerate(project_urls):
                    st.text(f"Scanning project {i+1}/{len(project_urls)}...")
                    
                    # Get procedure pages
                    procedure_urls = get_procedura_links(project_url, session)

                    for proc_url in procedure_urls:
                        # Get document links
                        doc_urls = get_document_links(proc_url, session)
                        
                        # Store results
                        for doc_url in doc_urls:
                            results.append({
                                'project_url': project_url,
                                'procedure_url': proc_url,
                                'document_url': doc_url,
                                'project_number': i+1
                            })

                # Display results in a organized way
                st.success(f"Found {len(results)} documents across {len(project_urls)} projects")
                
                # Group documents by project
                for i in range(len(project_urls)):
                    project_docs = [r for r in results if r['project_number'] == i+1]
                    if project_docs:
                        with st.expander(f"Project #{i+1} - {len(project_docs)} documents"):
                            for doc in project_docs:
                                col1, col2 = st.columns([4, 1])
                                with col1:
                                    st.markdown(f"📄 Document: `{doc['document_url'].split('/')[-1]}`")
                                with col2:
                                    # Create direct download link
                                    st.markdown(f"[Download]({doc['document_url']})")
                                st.markdown("---")

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.error("Debug info:")
            import traceback
            st.code(traceback.format_exc())