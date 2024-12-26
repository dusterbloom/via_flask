import streamlit as st
from scraper import get_projects, get_procedura_links, get_document_links
import time

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
                            
                            # Display documents
                            for doc in project_docs:
                                col1, col2, col3 = st.columns([3, 2, 1])
                                with col1:
                                    st.markdown(f"**{doc['title']}**")
                                with col2:
                                    st.markdown(f"""
                                    📅 {doc['date']}  
                                    📁 {doc['type']}  
                                    💾 {doc['size']}
                                    """)
                                with col3:
                                    st.markdown(f"[Download]({doc['url']})")
                                st.markdown("---")

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.error("Debug info:")
            import traceback
            st.code(traceback.format_exc())