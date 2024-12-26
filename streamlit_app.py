import streamlit as st
from scraper import get_projects, get_procedura_links, get_document_links
import time
from datetime import datetime

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

def format_date(date_str):
    try:
        # Adjust the parsing format based on the actual date format
        date_obj = datetime.strptime(date_str, '%d/%m/%Y')
        return date_obj.strftime('%d %b %Y')
    except:
        return date_str

if search_button and keyword:
    keyword = keyword.strip()
    if not keyword:
        st.error("Please enter a valid keyword.")
    else:
        try:
            with st.spinner("Searching for projects..."):
                project_urls, session = get_projects(keyword)
                st.info(f"Found {len(project_urls)} projects")

                results = []

                # Process each project
                for i, project_url in enumerate(project_urls):
                    st.text(f"Scanning project {i+1}/{len(project_urls)}...")
                    
                    # Get procedure pages
                    procedure_urls = get_procedura_links(project_url, session)

                    for proc_url in procedure_urls:
                        # Get documents with metadata
                        documents = get_document_links(proc_url, session)
                        
                        # Store results
                        for doc in documents:
                            doc['project_url'] = project_url
                            doc['procedure_url'] = proc_url
                            doc['project_number'] = i+1
                            results.append(doc)

                # Display results
                st.success(f"Found {len(results)} documents across {len(project_urls)} projects")
                
                # Group documents by project
                for i in range(len(project_urls)):
                    project_docs = [r for r in results if r['project_number'] == i+1]
                    if project_docs:
                        with st.expander(f"Project #{i+1} - {len(project_docs)} documents"):
                            # Add project metadata if available
                            st.markdown(f"🔗 [View Project Details]({project_docs[0]['project_url']})")
                            st.markdown("---")
                            
                            # Create a clean table-like display for documents
                            for doc in project_docs:
                                col1, col2, col3 = st.columns([3, 2, 1])
                                with col1:
                                    st.markdown(f"**{doc['title']}**")
                                with col2:
                                    st.markdown(f"""
                                    📅 {format_date(doc['date'])}  
                                    📁 {doc['type']}  
                                    💾 {doc['size']}
                                    """)
                                with col3:
                                    st.markdown(f"[Download]({doc['url']})")
                                st.markdown("---")

                # Add filtering options
                st.sidebar.markdown("## Filters")
                if results:
                    # Get unique document types
                    doc_types = list(set(doc['type'] for doc in results if 'type' in doc))
                    selected_types = st.sidebar.multiselect(
                        "Filter by document type",
                        doc_types
                    )
                    
                    # Date range filter
                    dates = [datetime.strptime(doc['date'], '%d/%m/%Y') 
                            for doc in results if 'date' in doc]
                    if dates:
                        min_date = min(dates)
                        max_date = max(dates)
                        date_range = st.sidebar.date_input(
                            "Filter by date range",
                            value=(min_date, max_date)
                        )

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.error("Debug info:")
            import traceback
            st.code(traceback.format_exc())