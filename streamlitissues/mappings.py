
# mapping for the labels
label_options_emoji_mapping = {
    "feature": "🛠️",
    "bug": "🐛",
    "enhancement": "⚡",
    "docs": "📚",
    "components": "🧩",
    "other": "🌀"
}

# mapping for the issue state
state_options_emoji_mapping = {
        "open": ":material/adjust:",
        "closed": ":material/check_circle:"
    }

# mapping for the issue type
type_options_emoji_mapping = {
         "issue": "🤧",
         "pull_request": "🔀"
    }

# mapping for the sorting options
# keys are the options that the user sees
# values are tuples where the first element is the column to sort by and the second element is the ascending flag
sorting_mapping = {
    "Newest First": ("created_at", True), 
    "Oldest First": ("created_at", False),
    "Most Reactions First": ("reaction_total_count", False),
    "Most Recently Updated First": ("updated_at", False),
}

# mapping for the chat avatars
avatar_mapping = {
    "user": None,
    "ai": "🎈"
}
    
# mapping for the model token sizes
model_token_sizes = {
    "mistral-7b": 32000,
    "mistral-large": 32000,
    "mistral-large2": 128000,
    "mixtral-8x7b": 32000,
    "llama2-70b-chat": 4096,
    "llama3.2-1b": 128000,
    "llama3.2-3b": 128000,
    "gemma-7b": 8000,
    "snowflake-arctic": 4096,
}