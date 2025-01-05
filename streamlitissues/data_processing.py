import pandas as pd
import re
import ast
from tqdm.auto import tqdm


class IssueProcessor:

    # Define the columns to keep in the processed data
    columns = [
        'id',
        'number', 
        'title', 
        'body', 
        'closed_at', 
        'comments',
        'comments_url', 
        'created_at',
        'html_url',
        'labels', 
        'pull_request', 
        'raw_data',
        'reactions', 
        'state',
        'state_reason', 
        'updated_at', 
        ]
    
    # Define the categories and their corresponding keywords
    label_categories = {
        'feature': ['feature', 'change:feature'],
        'enhancement': ['enhancement', 'improvement'],
        'bug': ['bug', 'fix', 'error'],
        'docs': ['docs', 'documentation'],
        'components': ['components', 'custom-components'],
        'other': []  # 'other' will be the default category
        }
    
    def __init__(self, data):
        self.data = data

        self.processed_data = self.process()

    def process(self):
        # Do some processing

        # Parse the raw_data column and convert to a dictionary
        data = self.parse_raw_data_column(self.data)

        # Filter the columns to keep only the relevant ones
        data = self.filter_columns(data)

        # process the labels column to extract and categorize the labels
        data = self.process_labels(data)
        # data = self.one_hot_encode_label_categories(data)

        # extract the pull request URL and reaction count from the raw_data column
        data = self.extract_pull_request_url(data)
        data = self.extract_reaction_total_count(data)

        # create a column for training a cortex model
        data = self.create_cortex_training_data(data)
        return data
    
    @staticmethod
    def parse_raw_data_column(data):
        """Parse the raw_data column into dictionaries.
        Parameters:
        data (pd.DataFrame): The input dataframe.

        Returns:
        pd.DataFrame: The dataframe with the raw_data parsed as dictionaries.
        """
        data['raw_data'] = data['raw_data'].apply(ast.literal_eval)
        return data

    @staticmethod
    def extract_labels(label_string):
        """Extract the labels from the label string.
        Parameters:
        label_string (str): A string containing the labels.

        Returns:
        list: A list of labels.

        example:
        extract_labels('[Label(name="change:feature"), Label(name="type:bug")]') 
        -> ['change:feature', 'type:bug']
        """
        # Extract the label using the regular expression pattern
        # example: [Label(name="change:feature"), Label(name="type:bug")]
        pattern = r'name="([^"]+)"'
        matches = re.findall(pattern, label_string)
        return matches

    def categorize_label(self, label_name):
        """Categorize the label based on the keywords in the label name.
        Parameters:
        label_name (str): The name of the label to categorize.
        
        Returns:
        str: The category of the label

        example:
        categorize_label('change:feature') -> 'feature'
        """
        

        # Convert the label name to lowercase for case-insensitive matching
        label_name_lower = label_name.lower()
        # Check each category for matching keywords
        for category, keywords in self.label_categories.items():
            if any(keyword in label_name_lower for keyword in keywords):
                return category
        # If no keywords match, return 'other'
        return 'other'
    
    def one_hot_encode_label_categories(self, data, label_column="label_categories"):
        """
        One-hot encode a column containing lists of categories using label categories.

        Parameters:
        data (pd.DataFrame): The input dataframe.
        column (str): The column name containing category lists.
        categories (list): The predefined list of categories.

        Returns:
        pd.DataFrame: The dataframe with new one-hot encoded columns.
        """
        # Create one-hot encoded columns for known categories
        for category in tqdm(self.label_categories):
            new_col = f"label_is_{category}"  # Create column name
            data[new_col] = data[label_column].apply(lambda x: bool(category in x))
        
        return data

    def process_labels(self, data=None):
        """Process the labels in the data.
        Extract the labels and categorize them.
        """
        if data is None:
            data = self.data

        data['labels'] = data['labels'].apply(self.extract_labels)
        data['label_categories'] = data['labels'].apply(
            lambda labels: [self.categorize_label(label) for label in labels]
        )
        return data
    
    def extract_pull_request_url(self, data=None):
        """Add the pull_request_url column to the dataframe.
        Parameters:
        data (pd.DataFrame): The input dataframe.

        Returns:
        pd.DataFrame: The dataframe with the pull_request_url column added.
        """
        if data is None:
            data = self.data
        data['pull_request_url'] = data['raw_data'].apply(
            lambda raw: raw.get('pull_request', {}).get('html_url') if isinstance(raw, dict) else None
        )
        # if pull request url is not None, set type to 'pull_request' else 'issue'
        data['type'] = data['pull_request_url'].apply(lambda x: 'pull_request' if x is not None else 'issue')
        return data

    def extract_reaction_total_count(self, data=None):
        """Add the reaction_total_count column to the dataframe.
        Parameters:
        data (pd.DataFrame): The input dataframe.

        Returns:
        pd.DataFrame: The dataframe with the reaction_total_count column added.
        """
        if data is None:
            data = self.data
        data['reaction_total_count'] = data['raw_data'].apply(
            lambda raw: raw.get('reactions', {}).get('total_count', 0) if isinstance(raw, dict) else 0
        )
        return data
    
    def create_cortex_training_data(self, data=None):
        """create a column from raw data for training a cortex model."""
        if data is None:
            data = self.data
        data['cortex_data'] = data['raw_data'].apply(
            lambda raw: {
                'title': raw.get('title', ''),
                'body': raw.get('body', ''),
                'labels': [label.get('name', '') for label in raw.get('labels', [])],
            }
        ).astype(str)

        return data
    
    def filter_columns(self, data=None, columns=None):
        """Filter the columns of the processed data.
        Parameters:
        columns (list): A list of columns to keep.

        Returns:
        pd.DataFrame: A DataFrame with the specified columns.
        """
        if data is None:
            data = self.data
        if columns is None:
            columns = self.columns
        return data[columns]