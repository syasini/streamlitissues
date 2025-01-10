import pandas as pd
import streamlit as st

from streamlitissues.mappings import (
    sorting_mapping,
    label_options_emoji_mapping,
    state_options_emoji_mapping,
    type_options_emoji_mapping,
    avatar_mapping,
    model_token_sizes,
)
from streamlitissues.utils import (
    build_context_column,
    create_snowflake_session_root,
    query_cortex_search_service,
    parse_label_categories,
    build_prompt,
    get_response_from_cortex,
    join_issue_bodies_for_context,
    show_limit_warning,
)

# fetch snowflake connection parameters from secrets
snowflake_parameters = dict(st.secrets["snowflake"])

# create a snowflake root object
snowflake_session, snowflake_root = create_snowflake_session_root(snowflake_parameters)

# create the cortex search query params
cortex_service_params = dict(st.secrets["cortex"])

# Streamlit app title and logo
_, col, _ = st.columns([1, 2, 1])
col.image("./media/logo.png", width=500)
st.title("What seems to be your Streamlit issue?")

# Initialize the search results and counter session states
if "results" not in st.session_state:
    st.session_state["results"] = None

if "search_counter" not in st.session_state:
    st.session_state["search_counter"] = 0

SEARCH_LIMIT = 5
# ---------------------------------------------------------------------------- #
#                                StreamliTissues                               #
# ---------------------------------------------------------------------------- #

# Let the fun begin!

# ----------------------------- Search Form ----------------------------- #


def submit_search_query():
    """Callback function to submit the search query.
    This is defined to allow keeping track of the search counter.
    """
    query = st.session_state["search_query"]  # defined in the form
    if query:
        # query the cortext search service
        response = query_cortex_search_service(
            snowflake_root=snowflake_root,
            query_service_params=cortex_service_params,
            query=query,
        )

        # store the results in the session state and increment the search counter
        st.session_state["results"] = response["results"]
        st.session_state["search_counter"] += 1

    else:
        st.warning("Hmm, did you forget to enter a search query? 🤔")


with st.form("search_form"):
    query = st.text_input(
        "Enter your search query:",
        key="search_query",
        placeholder="Ugh, the Streamlit widgetamajig doesn't work! 😭",
    )

    # calculate the remaining searches and show a warning if the limit is reached
    remaining_searches = SEARCH_LIMIT - st.session_state["search_counter"]
    if remaining_searches < 0:
        show_limit_warning()

    # add a submit button to trigger the search
    submit_button = st.form_submit_button(
        label=f"Search ({remaining_searches if remaining_searches >= 0 else 0} Remaining)",
        disabled=bool(remaining_searches < 0),
        on_click=submit_search_query,
    )

# ---------------------------------- Filters --------------------------------- #

# filter the results after the search for cost efficiency
with st.expander("Filter and Sort Results"):
    filter_col_l, filter_col_r = st.columns(2)

    # add filter for issue labels: feature, bug, enhancement, docs, components, other
    label_options = list(label_options_emoji_mapping.keys())
    label_filter_list = filter_col_l.pills(
        "Labels",
        label_options,
        selection_mode="multi",
        default=["feature", "bug", "enhancement"],
        format_func=lambda x: label_options_emoji_mapping[x] + " " + x,
    )

    # add filter for issue state: open, closed
    state_options = list(state_options_emoji_mapping.keys())
    state_filter_list = filter_col_l.segmented_control(
        "State",
        state_options,
        default=state_options,
        selection_mode="multi",
        format_func=lambda x: state_options_emoji_mapping[x] + " " + x,
    )

    # add filter for issue type: issue, pull_request
    type_options = list(type_options_emoji_mapping.keys())
    type_filter_list = filter_col_l.pills(
        "Type",
        type_options,
        selection_mode="multi",
        default="issue",
        format_func=lambda x: type_options_emoji_mapping[x] + " " + x,
    )

    # add filter for number of results
    n_results = filter_col_r.slider(
        "Limit Results to ", min_value=5, max_value=20, value=10, step=5
    )

    # add sorting options
    sorting_option = filter_col_r.selectbox(
        "Sort By",
        [
            "Most Relevant First",
            "Newest First",
            "Oldest First",
            "Most Reactions First",
            "Most Recently Updated First",
        ],
    )

# -------------------------------- Chat Option ------------------------------- #

# add a toggle to enable chat with the issues
_, chat_col = st.columns(2)
chat_toggle = chat_col.toggle("Chat with issues", value=False)
if chat_toggle:
    with chat_col:
        # allow the user to select a model for the chat
        model_name = st.selectbox(
            "Select a model", options=model_token_sizes.keys(), index=2
        )
        # add a button to reset the chat
        if st.button("Reset Chat", type="primary"):
            st.session_state["messages"] = st.session_state["messages"][:2]

# create columns for the issues and chat
if chat_toggle:
    issue_col, chat_col = st.columns(2)
else:
    issue_col, chat_col = st, None  # this feels a bit hacky, but seems to work...


# ---------------------------- Process the Results --------------------------- #

# define results variable for convenience
results = st.session_state["results"]

if results is not None:
    # convert the results to a DataFrame for easier filtering and sorting
    results_df = pd.DataFrame(results)
    
    # parse the label_categories column: remove [ and ] and split by ',' and remove duplicates
    results_df["label_categories"] = results_df["label_categories"].apply(
        parse_label_categories
    )

    # ----------------------- apply the filters and sorting ---------------------- #
    # NOTE: the filters acts as an OR operator

    # make sure each selected label is in the label_categories column
    results_df = results_df[
        results_df["label_categories"].apply(
            lambda x: any(label in x for label in label_filter_list)
        )
    ]

    # make sure each selected state is in the state column
    results_df = results_df[results_df["state"].isin(state_filter_list)]

    # make sure each selected type is in the type column
    results_df = results_df[results_df["type"].isin(type_filter_list)]

    # sort the results (default results are sorted by relevance directly from Snowflake)
    sorting_key, ascending = sorting_mapping.get(sorting_option, (None, None))
    results_df["reaction_total_count"] = results_df["reaction_total_count"].fillna("0").astype(int)
    
    if sorting_key is not None:
        results_df = results_df.sort_values(by=sorting_key, ascending=ascending)

    
    # limit the number of results
    results_df = results_df.head(n_results)
    # ---------------------------- Display the Results ---------------------------- #
    for _, result in results_df.iterrows():
        # get the emoji for the type and state to add to the title in expanders
        type_emoji = type_options_emoji_mapping[result["type"]]
        state_emoji = state_options_emoji_mapping[result["state"]]
        labels_emoji_list = [
            label_options_emoji_mapping[label]
            for label in result["label_categories"]
            if label in label_options
        ]

        # create the fancy expander title with the emojis and stuff
        title = f"**{result['title']}** [\#{result['number']}  |  {state_emoji} {type_emoji}  |  {' '.join(labels_emoji_list)}]"

        with issue_col.expander(
            title,
            expanded=False,
        ):
            # display additional issue details
            created_at = pd.to_datetime(result["created_at"]).strftime("%B %d, %Y")
            reaction_count = result["reaction_total_count"]
            st.write(f"🗓️ {created_at}  |  👍 {reaction_count}")

            # display the link to Github and finally! the issue body
            st.caption("See the full issue on GitHub:")
            st.info(result["html_url"], icon="🔗")
            st.divider()
            st.caption("Issue Description")
            st.markdown(result["body"])

# --------------------------- Chat with the issues --------------------------- #

if chat_col is not None:
    # add a password to the chat to prevent unauthorized access (for cost considerations, you know...)
    chat_password = st.sidebar.text_input("Enter Chat password", type="password")
    if chat_password == cortex_service_params["chat_password"] or cortex_service_params["by_pass_password"]:
        # make sure there are search results to chat with
        if results is None:
            chat_col.warning("Please search for issues first.")
        else:
            # create a chat container to display the messages
            messages = chat_col.container(height=700)

            # initialize the messages session state
            if "messages" not in st.session_state:
                st.session_state["messages"] = [
                    {
                        "role": "ai",
                        "content": "*[Sigh]* Hi there… I'm yet another AI assistant, trying my best to help you make sense of whatever you just searched for. \
                        Frankly, I don't know why this app has such a silly name, so don't ask me that…",
                    },
                    {
                        "role": "ai",
                        "content": "If you're having a hard time reading the text in this teeny-tiny window, you can switch the app to wide mode. \
                        How else may I help you today?",
                    },
                ]

            # display the previous chat messages
            for message in st.session_state.messages:
                with messages.chat_message(
                    message["role"], avatar=avatar_mapping[message["role"]]
                ):
                    st.markdown(message["content"])

            # add a chat input to allow the user to chat with the issues
            if prompt := chat_col.chat_input("Speak your mind..."):
                st.session_state.messages.append({"role": "user", "content": prompt})
                with messages.chat_message("user", avatar=avatar_mapping["user"]):
                    st.markdown(prompt)

                # concat the columns title, body, and labels to build the context
                # for some reason cotex_data is being returned as empty strings by cortex
                # the new columns will be stores as 
                # "title: <title column> body: <body column> label_categories: <label_categories column>"
                results_df["context"] = build_context_column(results_df)    
                     
                context = join_issue_bodies_for_context(results_df["context"].tolist())

                # Build the LLM prompt
                prompt_text = build_prompt(prompt, context)

                # Get the response from Snowflake Cortex and display it
                with messages.chat_message("ai", avatar=avatar_mapping["ai"]):
                    with st.spinner("thinking..."):
                        response = get_response_from_cortex(
                            prompt_text,
                            model_name=model_name,
                            snowflake_session=snowflake_session,
                            cortex_service_params=cortex_service_params,
                        )

                        st.session_state.messages.append(
                            {"role": "ai", "content": response}
                        )
                        st.markdown(response)

    elif chat_password == "":
        chat_col.warning("Please enter the chat password to use the chat function.")
    else:
        chat_col.warning(
            "Chat password is incorrect. Did someone gave you the wrong password? or did you just try to randomly guess it? 🤔"
        )
