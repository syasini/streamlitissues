
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
        "open": "☐",
        "closed": "☑"
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