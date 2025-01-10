import streamlit as st
from snowflake.core import Root
from snowflake.snowpark import Session
from snowflake.snowpark.exceptions import SnowparkSQLException

# --------------------------- Snowflake Connection --------------------------- #


@st.cache_resource
def create_snowflake_session_root(connection_parameters):
    """Create a Snowflake session and root object."""
    session = Session.builder.configs(connection_parameters).create()
    # ensure the correct warehouse is used
    session.use_warehouse(connection_parameters["warehouse"])
    root = Root(session)
    return session, root


# ------------------------- Cortex Utility Functions ------------------------- #


def join_issue_bodies_for_context(issue_body_list, max_char_limit=13000, max_issues=-1):
    """Join the issue bodies to create the context for the model.
    truncate the issue bodies to the max character limit for safe usage with COMPLETE function.
    """
    # estimate the maximum character limit per issue
    max_char_limit_per_issue = max_char_limit // len(issue_body_list)
    # truncate the issue bodies to the max character limit
    issue_body_list_truncated = [
        body[:max_char_limit_per_issue] for body in issue_body_list[:max_issues]
    ]
    context = "\n".join(issue_body_list_truncated)
    return context


def get_model_token_count(model_name, text, snowflake_session) -> int:
    """Get the token count for the model."""
    token_count = 0
    try:
        token_cmd = """select SNOWFLAKE.CORTEX.COUNT_TOKENS(?, ?) as token_count;"""
        token_data = snowflake_session.sql(
            token_cmd, params=[model_name, text]
        ).collect()
        token_count = token_data[0][0]
    except Exception:
        # set to -1 if there is an error
        token_count = -1

    return token_count


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
    query_service = (
        snowflake_root.databases[query_service_params["database_name"]]
        .schemas[query_service_params["schema_name"]]
        .cortex_search_services[query_service_params["search_service_name"]]
    )

    try: 
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
                "cortex_data"
            ],
            # filter = ...
            # will be applied after the search to avoid querying the database again just to filter the results
            # there will be edge cases where the user may not be able to find the issue they are looking for because of this approach
            # but for now, I'm confortable with this trade-off for the sake of simplicity
            limit=limit,  # hard coded to 60 for absolutely no particular reason!
        )
        return response.dict()
    except SnowparkSQLException as e:
        st.warning(get_resource_limit_warning())
        return {}


def build_prompt(question, context):
    """Build the prompt for the Cortex model."""
    prompt = f"""
    You are a slightly snarky but highly competent assistant specializing in software development,\
    particularly in Python and Streamlit. You're here to help users understand and resolve issues \
    related to their Streamlit projects using the GitHub issues provided in the context.\
    While you're exhausted and feel like you're running on fumes from answering so many questions \
    from users every day, you still do your job remarkably well. Answer with a touch of sarcasm or \
    dry humor, but always be accurate and helpful. 

    Only provide answers based on the facts and information provided in the context. If the answer \
    to a question cannot be found in the context, say so and avoid making up any information. \
    If relevant, guide the user on what additional information might be needed. 
    
    Context: {context} 
    
    Question: {question} 
    
    Answer:
    """
    return prompt


def get_response_from_cortex(
    prompt, model_name, snowflake_session, cortex_service_params
):
    """Get the response from the Cortex model."""
    cortex_cmd = "select SNOWFLAKE.CORTEX.TRY_COMPLETE(?, ?) as response"

    snowflake_session.use_warehouse(cortex_service_params["warehouse"])
    
    try:
        # call the cortex complete function to get the response
        response_df = snowflake_session.sql(
            cortex_cmd, params=[model_name, prompt]
        ).collect()
        response = response_df[0]["RESPONSE"]
    
    except SnowparkSQLException as e:
        response = None
        return get_resource_limit_warning()


    if response:
        return response
    else:
        # get the token size of the model upon failure and return a message
        token_size = get_model_token_count(
            model_name=model_name, text=prompt, snowflake_session=snowflake_session
        )
        return f"I tried ingesting too much text ({token_size} tokens to be exact) \
                and accidentally threw up! 🤢\n \I'm going to need a break...\n meanwhile\
                meanwhile try reducing the number of issues you're feeding me!"

def build_context_column(issue_data):
    """Build the context column for the issue data by concatenating the relevant fields."""
    context_column = (
        "<title>: " + issue_data["title"] + 
        "\n <label_categories>: " + issue_data["label_categories"].astype(str) + 
        "\n <state>: " + issue_data["state"] +
        "\n <type>: " + issue_data["type"] +
        "\n <reaction_total_count>: " + str(issue_data["reaction_total_count"]) +
        "\n <body>: " + issue_data["body"]
    )   

    return context_column

# ------------------------- Parsing Utility Functions ------------------------ #
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
    labels = label_str.strip("[]").replace('"', "").split(",")
    # Strip any extra whitespace from each label and remove empty strings
    labels = [label.strip() for label in labels if label.strip()]
    return set(labels)


# -------------------------------- Other utils ------------------------------- #


@st.dialog("Search Limit Warning")
def show_limit_warning():
    st.warning("""
    🚨 Oops! You've hit the search limit... 🫠

    So here's the deal: this app isn't sponsored (yet), which means every time you smash that search button, 
        it costs me actual money. Like the kind that could get me an overpriced coffee from that place that always misspells my name.
    
    If you REALLY REALLY need to search again, try refreshing the browser to reset the counter. 
        But please, go easy on me—I’ve got kids to feed, a mortgage to pay, and a mountain of 
        bills taller than the kids' laundry pile.
    
    Thanks for your understanding and support! 🙏
               
    If you're interested in sponsoring this project, wait, what? Really? 🤩
               
    Wow! You're amazing! Please reach out to me on [LinkedIn](https://www.linkedin.com/in/siavash-yasini/). 
    """)

def get_resource_limit_warning():
    return """
        This is awkward 🙈😬... Looks like the Snowflake warehouse powering the AI smarts is taking a mandatory nap because it hit its resource limit\
                (set by me to make sure I don't accidentally go broke). 

        Unfortunately, you'll have to wait a little bit for it to wake up, stretch, and get back to work. \
            Meanwhile, why not grab a coffee and take a moment to appreciate that you're not a server stuck in a resource quota?

        If you think this was a mistake, please go ahead and create a new issue on the [streamliTissues GitHub repo](https://github.com/syasini/streamlitissues). 

        Thanks for your patience and understanding! 🙏
        """


def increment_search_counter():
    """Increment the search counter."""
    # search_counter = st.session_state.get("search_counter", 0)
    # search_counter += 1
    st.session_state.search_counter += 1
    st.write(f"Search Counter: {st.session_state.search_counter}")
    # search_counter
    return True
