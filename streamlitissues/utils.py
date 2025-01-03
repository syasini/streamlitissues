import streamlit as st
from snowflake.core import Root
from snowflake.snowpark import Session


@st.cache_resource
def create_snowflake_session_root(connection_parameters):
    """Create a Snowflake session and root object."""
    session = Session.builder.configs(connection_parameters).create()
    root = Root(session)
    return root


def query_cortex_search_service(snowflake_root, query_service_params, query, limit=60):
    """Query the cortex search service.
    Parameters:
    snowflake_root (Root): The root object for the Snowflake session.
    query (str): The search query.
    limit (int): The maximum number of results to return.
    
    Returns:
    dict: The search results.
    """
    # connect to the query service object using the snowflake root
    query_service = (snowflake_root
        .databases[query_service_params["database_name"]]
        .schemas[query_service_params["schema_name"]]
        .cortex_search_services[query_service_params["search_service_name"]]
        )

    # search for the query
    response = query_service.search(
        query=query,
        columns=[
            "number",
            "title",
            "body",
            "state",
            "html_url",
            "closed_at",
            "created_at",
            "html_url",
            "updated_at",
            "label_categories",
            "type",
            "reaction_total_count",     
        ],
        # filter = ...
            # will be applied after the search to avoid querying the database again just to filter the results
            # there will be edge cases where the user may not be able to find the issue they are looking for because of this approach
            # but for now, I'm confortable with this trade-off for the sake of simplicity
        limit=limit  # hard coded to 60 for absolutely no particular reason! 
        )
    return response.dict()

def parse_label_categories(label_str):
    """Parse the label categories from the raw data.
    Parameters:
    label_str (str): The raw label string.
    
    Returns:
    set: The set of label categories.

    Example:
    '["feature", "bug", "enhancement"]'  ->  {"feature", "bug", "enhancement"}
    """
    # Remove the square brackets and split by comma
    labels = label_str.strip("[]").replace('"', '').split(",")
    # Strip any extra whitespace from each label and remove empty strings
    labels = [label.strip() for label in labels if label.strip()]
    return set(labels)