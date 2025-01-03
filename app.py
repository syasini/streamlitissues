import pandas as pd
import streamlit as st

from streamlitissues.mappings import sorting_mapping, label_options_emoji_mapping, state_options_emoji_mapping, type_options_emoji_mapping
from streamlitissues.utils import create_snowflake_session_root, query_cortex_search_service, parse_label_categories


# fetch snowflake connection parameters from secrets
snowflake_parameters = dict(st.secrets["snowflake"]) 

# create a snowflake root object
snowflake_root = create_snowflake_session_root(snowflake_parameters)

# create the cortex search query params
cortex_service_params = dict(st.secrets["cortex"])

# Streamlit app title and logo
st.image("./media/logo-medium.png",)
st.title("What seems to be the issue?")

# Initialize the search results and counter session states
if "results" not in st.session_state:
    st.session_state["results"] = None
    
if "search_counter" not in st.session_state:
    st.session_state["search_counter"] = 0

# ---------------------------------------------------------------------------- #
#                                StreamliTissues                               #
# ---------------------------------------------------------------------------- #

# Let the fun begin! 

# ----------------------------- Search Form ----------------------------- #
search_form = st.form("search_form")
query = search_form.text_input("Enter your search query:", 
                          placeholder="Ugh, the Streamlit widgetamajig doesn't work! 😭")
    
submit_button = search_form.form_submit_button(label=f"Search")
if submit_button:
    if query:
        # query the cortext search service
        response = query_cortex_search_service(snowflake_root=snowflake_root, 
                                               query_service_params=cortex_service_params,
                                               query=query)
        st.session_state["results"] = response["results"]
        # st.write(st.session_state["search_counter"])
        st.session_state["search_counter"] += 1
    else:
        st.warning("Hmm, did you forget to enter a search query? 🤔")
    

# ---------------------------------- Filters --------------------------------- #
    
# filter the results after the search for cost efficiency
with st.expander("Filter and Sort Results"):
    filter_col_l, filter_col_r = st.columns(2)

    # add filter for issue labels: feature, bug, enhancement, docs, components, other
    label_options = list(label_options_emoji_mapping.keys())
    label_filter_list = filter_col_l.pills("Labels", 
                                           label_options, 
                                           selection_mode="multi", 
                                           default=['feature', "bug", 'enhancement'],
                                           format_func=lambda x: label_options_emoji_mapping[x] + " " + x)

    # add filter for issue state: open, closed
    state_options = list(state_options_emoji_mapping.keys())
    state_filter_list = filter_col_l.segmented_control("State", 
                                                       state_options, 
                                                       default=state_options, 
                                                       selection_mode="multi",
                                                       format_func=lambda x: state_options_emoji_mapping[x] + " " + x)
    
    # add filter for issue type: issue, pull_request
    type_options = list(type_options_emoji_mapping.keys())
    type_filter_list = filter_col_l.pills("Type",
                                          type_options, 
                                          selection_mode="multi", 
                                          default="issue",
                                          format_func=lambda x: type_options_emoji_mapping[x] + " " + x)
    
    # add filter for number of results
    n_results = filter_col_r.slider("Limit Results to ", min_value=5, max_value=30, value=10, step=5)

    # add sorting options
    sorting_option = \
        filter_col_r.selectbox("Sort By", [
                    "Most Relevant First",
                    "Newest First", 
                    "Oldest First", 
                    "Most Reactions First",
                    "Most Recently Updated First",
                    ])
    
# -------------------------------- Chat Option ------------------------------- #

# add a toggle to enable chat with the issues
chat_toggle = st.toggle("Chat with issues", value=False)

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
    results_df["label_categories"] = results_df["label_categories"].apply(parse_label_categories)
    
    # ----------------------- apply the filters and sorting ---------------------- #
    # NOTE: the filters acts as an OR operator

    # make sure each selected label is in the label_categories column
    results_df = results_df[results_df["label_categories"].apply(lambda x: any(label in x for label in label_filter_list))]
    
    # make sure each selected state is in the state column
    results_df = results_df[results_df["state"].isin(state_filter_list)]
    
    # make sure each selected type is in the type column
    results_df = results_df[results_df["type"].isin(type_filter_list)]

    # sort the results (default results are sorted by relevance directly from Snowflake)
    sorting_key, ascending = sorting_mapping.get(sorting_option, (None, None))
    if sorting_key is not None:
        results_df = results_df.sort_values(by=sorting_key, ascending=ascending)

    # limit the number of results
    results_df = results_df.head(n_results)

    # ---------------------------- Display the Results ---------------------------- #
    for _, result in results_df.iterrows():
        # get the emoji for the type and state to add to the title in expanders
        type_emoji = type_options_emoji_mapping[result["type"]]
        state_emoji = state_options_emoji_mapping[result["state"]]
        labels_emoji_list = [label_options_emoji_mapping[label] for label in result["label_categories"] if label in label_options]

        # create the fancy expander title with the emojis and stuff
        title = f"**{result['title']}** [\#{result['number']}  |  {state_emoji} {type_emoji}  |  {' '.join(labels_emoji_list)}]"

        with issue_col.expander(title, expanded=False, ):
            # display additional issue details
            created_at = pd.to_datetime(result["created_at"]).strftime("%B %d, %Y")
            reaction_count = result["reaction_total_count"]
            st.write(f"🗓️ {created_at}  |  👍 {reaction_count}" )

            # display the link to Github and finally! the issue body
            st.caption("See the full issue on GitHub:")
            st.info(result["html_url"], icon="🔗")
            st.divider()
            st.caption("Issue Description")
            st.markdown(result["body"])

